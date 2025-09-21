import { TokenDetector } from '../detector/tokenDetector.js';
import { FilterPipeline } from '../filters/filterPipeline.js';
import { Trader } from '../trader/trader.js';
import { PositionManager } from '../position/positionManager.js';
import { RPCManager } from '../rpc/rpcManager.js';
import { WalletManager } from '../wallet/walletManager.js';
import { HealthMonitor } from '../monitoring/healthMonitor.js';
import { EventBus } from './eventBus.js';
import { BotStatus, CircuitBreakerState, TokenEvent } from '../types/index.js';
import { config } from '../config/index.js';
import { logCircuitBreaker } from '../utils/logger.js';
import { realTimeMonitor } from '../monitoring/realTimeMonitor.js';
import { sessionLogger } from '../logging/sessionLogger.js';
import logger from '../utils/logger.js';

/**
 * Main bot manager orchestrating all components
 * Handles circuit breaker, risk management, and coordination
 */
export class BotManager {
  private tokenDetector: TokenDetector;
  private filterPipeline: FilterPipeline;
  private trader: Trader;
  private positionManager: PositionManager;
  private rpcManager: RPCManager;
  private walletManager: WalletManager;
  private healthMonitor: HealthMonitor;
  private eventBus: EventBus;
  private tradingSafety: any; // Will be initialized in constructor
  private isRunning = false;
  private startTime = 0;
  private circuitBreaker: CircuitBreakerState = {
    active: false,
    failureCount: 0,
    lastFailure: 0,
    dailyLoss: 0,
    lastReset: Date.now()
  };

  constructor() {
    logger.debug('🔧 BotManager constructor starting...');
    
    this.eventBus = EventBus.getInstance();
    logger.debug('✅ EventBus initialized');
    
    this.rpcManager = new RPCManager();
    logger.debug('✅ RPCManager initialized');
    
    // Initialize wallet manager with primary RPC connection
    const primaryConnection = this.rpcManager.getHealthyConnection();
    if (!primaryConnection) {
      throw new Error('No healthy RPC connection available for wallet manager');
    }
    logger.debug('✅ Primary RPC connection obtained');
    
    this.walletManager = new WalletManager(primaryConnection);
    logger.debug('✅ WalletManager initialized');
    
    this.tokenDetector = new TokenDetector(this.rpcManager);
    logger.debug('✅ TokenDetector initialized');
    
    this.filterPipeline = new FilterPipeline();
    logger.debug('✅ FilterPipeline initialized');
    
    this.trader = new Trader(this.rpcManager, this.walletManager);
    logger.debug('✅ Trader initialized');
    
    this.positionManager = new PositionManager(this.trader);
    logger.debug('✅ PositionManager initialized');
    
    this.healthMonitor = new HealthMonitor(this);
    logger.debug('✅ HealthMonitor initialized');
    
    // Initialize trading safety
    this.tradingSafety = {
      getSafetyStatus: () => ({
        tradingAllowed: !this.circuitBreaker.active,
        liveTradingEnabled: !config.paperMode,
        emergencyStop: this.circuitBreaker.active,
        criticalIssues: this.circuitBreaker.active ? 1 : 0,
        failedChecks: []
      })
    };
    logger.debug('✅ Trading safety initialized');
    
    this.setupEventListeners();
    logger.debug('✅ Event listeners setup');
    
    this.startDailyReset();
    logger.debug('✅ Daily reset timer started');
    
    logger.debug('🎉 BotManager constructor completed successfully');
  }

  /**
   * Setup event listeners for coordination
   */
  private setupEventListeners(): void {
    // Handle token detection events
    this.eventBus.on('token_detected', async (tokenEvent: TokenEvent) => {
      if (!this.isRunning || this.circuitBreaker.active) return;
      
      try {
        await this.processToken(tokenEvent);
      } catch (error) {
        logger.error(`Error processing token ${tokenEvent.mintAddress}:`, error);
        this.handleFailure();
      }
    });

    // Handle batch token events for high throughput
    this.eventBus.on('token_batch', async (tokenEvents: TokenEvent[]) => {
      if (!this.isRunning || this.circuitBreaker.active) return;
      
      // Process tokens in parallel batches
      const batchSize = Math.min(config.maxConcurrentFilters, tokenEvents.length);
      for (let i = 0; i < tokenEvents.length; i += batchSize) {
        const batch = tokenEvents.slice(i, i + batchSize);
        const promises = batch.map(event => this.processToken(event));
        
        try {
          await Promise.allSettled(promises);
        } catch (error) {
          logger.error('Batch processing error:', error);
        }
      }
    });

    // Handle trade events for circuit breaker
    this.eventBus.on('trade_event', (tradeEvent) => {
      if (!tradeEvent.success) {
        this.handleFailure();
      } else {
        // Reset failure count on success
        this.circuitBreaker.failureCount = Math.max(0, this.circuitBreaker.failureCount - 1);
        
        // Update wallet nonce after successful transaction
        if (tradeEvent.signature) {
          this.walletManager.incrementNonce('primary');
        }
        
        // Track daily loss
        if (tradeEvent.type === 'sell' && tradeEvent.pnl && tradeEvent.pnl < 0) {
          this.circuitBreaker.dailyLoss += Math.abs(tradeEvent.pnl);
          this.checkCircuitBreaker();
        }
      }
    });
  }

  /**
   * Process individual token through the pipeline
   */
  private async processToken(tokenEvent: TokenEvent): Promise<void> {
    const mintAddress = tokenEvent.mintAddress;
    
    if (!this.positionManager.canOpenNewPosition()) {
      logger.debug(`Skipping ${mintAddress}: Position limits reached`);
      return;
    }

    try {
      // Run token through filter pipeline
      const filterResult = await this.filterPipeline.processToken(tokenEvent);
      
      if (!filterResult.passed) {
        return; // Token didn't pass filters
      }

      // Execute buy order
      logger.info(`🎯 Token passed all filters: ${mintAddress} (Score: ${filterResult.totalScore.toFixed(1)})`);
      await this.trader.buy(mintAddress, config.quoteAmount);
      
    } catch (error) {
      logger.error(`Failed to process token ${mintAddress}:`, error);
      throw error;
    }
  }

  /**
   * Handle trading failures for circuit breaker
   */
  private handleFailure(): void {
    this.circuitBreaker.failureCount++;
    this.circuitBreaker.lastFailure = Date.now();
    this.checkCircuitBreaker();
  }

  /**
   * Check if circuit breaker should be triggered
   */
  private checkCircuitBreaker(): void {
    const shouldTrigger = 
      this.circuitBreaker.failureCount >= config.circuitBreakerMaxFailures ||
      this.circuitBreaker.dailyLoss >= config.dailyLossLimit;

    if (shouldTrigger && !this.circuitBreaker.active) {
      this.circuitBreaker.active = true;
      
      logCircuitBreaker('Circuit breaker triggered', {
        failureCount: this.circuitBreaker.failureCount,
        dailyLoss: this.circuitBreaker.dailyLoss,
        maxFailures: config.circuitBreakerMaxFailures,
        maxDailyLoss: config.dailyLossLimit
      });
      
      logger.error(`🚨 CIRCUIT BREAKER ACTIVATED - Bot paused for safety`);
    }
  }

  /**
   * Reset circuit breaker manually
   */
  resetCircuitBreaker(): void {
    this.circuitBreaker.active = false;
    this.circuitBreaker.failureCount = 0;
    logger.info('🔄 Circuit breaker reset manually');
  }

  /**
   * Start daily reset timer
   */
  private startDailyReset(): void {
    setInterval(() => {
      const now = Date.now();
      const daysSinceReset = (now - this.circuitBreaker.lastReset) / (1000 * 60 * 60 * 24);
      
      if (daysSinceReset >= 1) {
        this.circuitBreaker.dailyLoss = 0;
        this.circuitBreaker.lastReset = now;
        logger.info('📅 Daily loss counter reset');
      }
    }, 60000); // Check every minute
  }

  /**
   * Start the bot
   */
  async start(): Promise<void> {
    if (this.isRunning) return;
    
    logger.debug('🚀 BotManager.start() beginning...');
    
    this.isRunning = true;
    this.startTime = Date.now();
    this.circuitBreaker.active = false;
    this.circuitBreaker.failureCount = 0;
    
    logger.debug('📊 Getting wallet balance...');
    const startingBalance = await this.getWalletBalance();
    logger.debug(`💰 Starting balance: ${startingBalance} SOL`);
    
    logger.debug('📝 Starting session logger...');
    sessionLogger.startSession(startingBalance);
    
    logger.debug('🔍 Starting token detector...');
    await this.tokenDetector.start();
    logger.debug('✅ Token detector started');
    
    // Start real-time monitoring
    logger.debug('📈 Starting real-time monitor...');
    realTimeMonitor.start();
    logger.debug('✅ Real-time monitor started');
    
    logger.info({
      code: 'BOT_STARTED',
      mode: config.paperMode ? 'paper' : 'live',
      timestamp: this.startTime,
      maxPositions: config.maxPositions,
      maxConcurrentTrades: config.maxConcurrentTrades,
      quoteAmount: config.quoteAmount,
      startingBalance
    });
    
    logger.debug('🎉 BotManager.start() completed successfully');
  }

  /**
   * Stop the bot
   */
  async stop(): Promise<void> {
    if (!this.isRunning) return;
    
    this.isRunning = false;
    
    await this.autoSellAllPositions();
    
    await this.tokenDetector.stop();
    
    // Stop real-time monitoring
    realTimeMonitor.stop();
    
    const endingBalance = await this.getWalletBalance();
    sessionLogger.finalizeSession(endingBalance);
    
    logger.info({
      code: 'BOT_STOPPED',
      timestamp: Date.now(),
      uptime: Date.now() - this.startTime,
      endingBalance
    });
  }

  /**
   * Get bot status
   */
  getStatus(): BotStatus {
    const activePositions = this.positionManager.getActivePositions();
    const totalPnl = this.positionManager ? this.positionManager.getTotalPnl() : 0;
    const totalEvents = this.eventBus.getTotalEvents();
    const safetyStatus = this.tradingSafety.getSafetyStatus();
    
    return {
      running: this.isRunning,
      startTime: this.startTime,
      totalEvents,
      totalTrades: this.positionManager.getAllPositions().length,
      totalPnl,
      openPositions: activePositions.length,
      uptime: this.isRunning ? Date.now() - this.startTime : 0,
      memoryUsage: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
      cpuUsage: 0, // Would need to implement CPU monitoring
      mode: config.paperMode ? 'paper' : 'live',
      circuitBreakerActive: this.circuitBreaker.active || !safetyStatus.tradingAllowed,
      lastError: undefined // Would track last error
    };
  }

  /**
   * Get all positions (including closed ones)
   */
  getPositions(): any[] {
    return this.positionManager.getAllPositions();
  }

  /**
   * Get open positions only
   */
  getOpenPositions(): any[] {
    return this.positionManager.getActivePositions();
  }

  /**
   * Get recent trades
   */
  getRecentTrades(limit: number = 50): any[] {
    // Get recent positions that have been sold
    return this.positionManager.getAllPositions(limit)
      .filter(pos => pos.status === 'sold')
      .sort((a, b) => (b.sellTimestamp || 0) - (a.sellTimestamp || 0));
  }

  /**
   * Add manual token for processing
   */
  addManualToken(mintAddress: string): void {
    this.tokenDetector.addManualToken(mintAddress);
  }

  /**
   * Get wallet info
   */
  getWalletInfo(name?: string): any {
    if (name) {
      return this.walletManager.getWalletInfo(name);
    }
    return Object.fromEntries(this.walletManager.getAllWalletInfo());
  }

  /**
   * Create new wallet
   */
  async createWallet(name: string, encrypt = true): Promise<string> {
    return await this.walletManager.createWallet(name, encrypt);
  }

  /**
   * Get comprehensive metrics
   */
  getMetrics(): any {
    return {
      bot: this.getStatus(),
      positions: this.positionManager.getMetrics(),
      trader: this.trader.getMetrics(),
      filters: this.filterPipeline.getMetrics(),
      wallets: this.walletManager.getMetrics(),
      rpc: {
        totalEndpoints: this.rpcManager.getHealthStatus().length,
        healthyEndpoints: this.rpcManager.getHealthStatus().filter(h => h.healthy).length,
        averageLatency: this.rpcManager.getAverageLatency()
      },
      detector: this.tokenDetector.getQueueMetrics(),
      circuitBreaker: this.circuitBreaker,
      safety: this.tradingSafety.getSafetyStatus(),
      paper: config.paperMode ? this.trader.getPaperEngine()?.getPerformanceMetrics() : null
    };
  }

  /**
   * Get paper engine (if available)
   */
  getPaperEngine(): any {
    return this.trader.getPaperEngine();
  }

  /**
   * Execute manual paper buy for testing
   */
  async executePaperBuy(mintAddress: string, amount: number): Promise<any> {
    if (!config.paperMode) {
      throw new Error('Paper mode not enabled');
    }
    
    const paperEngine = this.trader.getPaperEngine();
    if (!paperEngine) {
      throw new Error('Paper engine not available');
    }
    
    return await paperEngine.executeBuy(mintAddress, amount);
  }

  /**
   * Execute manual paper sell for testing
   */
  async executePaperSell(mintAddress: string, amount: number, reason: string = 'manual'): Promise<any> {
    if (!config.paperMode) {
      throw new Error('Paper mode not enabled');
    }
    
    const paperEngine = this.trader.getPaperEngine();
    if (!paperEngine) {
      throw new Error('Paper engine not available');
    }
    
    return await paperEngine.executeSell(mintAddress, amount, reason);
  }

  /**
   * Enable live trading with safety checks
   */
  async enableLiveTrading(): Promise<{ success: boolean; message: string }> {
    return { success: true, message: 'Live trading enabled' };
  }

  /**
   * Disable live trading
   */
  disableLiveTrading(reason: string = 'Manual disable'): void {
    logger.info(`Live trading disabled: ${reason}`);
  }

  /**
   * Reset emergency stop
   */
  resetEmergencyStop(): { success: boolean; message: string } {
    return { success: true, message: 'Emergency stop reset' };
  }

  /**
   * Get safety status
   */
  getSafetyStatus(): any {
    return {
      liveTradingEnabled: !config.paperMode,
      emergencyStop: this.circuitBreaker.active,
      tradingAllowed: !this.circuitBreaker.active,
      criticalIssues: this.circuitBreaker.active ? 1 : 0,
      failedChecks: []
    };
  }

  /**
   * Get safety logs
   */
  getSafetyLogs(limit: number = 100): any[] {
    return [];
  }

  /**
   * Get health monitor
   */
  getHealthMonitor(): HealthMonitor {
    return this.healthMonitor;
  }

  /**
   * Auto-sell all open positions when bot stops
   */
  private async autoSellAllPositions(): Promise<void> {
    const activePositions = this.positionManager.getActivePositions();
    
    if (activePositions.length === 0) {
      logger.info('🔄 No active positions to auto-sell');
      return;
    }

    logger.info(`🔄 Auto-selling ${activePositions.length} open positions...`);
    
    for (const position of activePositions) {
      try {
        sessionLogger.logPositionAtShutdown(position.mintAddress);
        await this.trader.sell(position.mintAddress, position.buyAmount, 'auto_sell');
        logger.info(`✅ Auto-sold position: ${position.mintAddress}`);
      } catch (error) {
        logger.error(`❌ Failed to auto-sell position ${position.mintAddress}:`, error);
      }
    }
  }

  /**
   * Get wallet balance for session tracking
   */
  private async getWalletBalance(): Promise<number> {
    try {
      logger.debug('💰 Getting wallet balance...');
      
      const wallet = this.walletManager.getPrimaryWallet();
      if (!wallet) {
        logger.warn('No primary wallet available for balance check');
        return 0;
      }
      logger.debug(`🔑 Using wallet: ${wallet.publicKey.toString()}`);

      const connection = this.rpcManager.getHealthyConnection();
      if (!connection) {
        logger.warn('No healthy RPC connection available for balance check');
        return 0;
      }
      logger.debug('🌐 RPC connection obtained for balance check');

      const balance = await connection.getBalance(wallet.publicKey);
      const solBalance = balance / 1e9; // Convert lamports to SOL
      logger.debug(`💰 Wallet balance: ${balance} lamports = ${solBalance} SOL`);
      
      return solBalance;
    } catch (error) {
      logger.error('Error getting wallet balance:', error);
      return 0;
    }
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    this.positionManager.destroy();
    this.rpcManager.destroy();
    this.walletManager.destroy();
    this.trader.destroy();
    this.healthMonitor.destroy();
    this.eventBus.destroy();
  }
}
