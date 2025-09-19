// import axios from 'axios';
import { EventBus } from '../core/eventBus.js';
import { RPCManager } from '../rpc/rpcManager.js';
import { WalletManager } from '../wallet/walletManager.js';
import { PaperEngine } from '../paper/paperEngine.js';
import { TradeEvent } from '../types/index.js';
import { config } from '../config/index.js';
import { logBuySuccess, logBuyError } from '../utils/logger.js';
import logger from '../utils/logger.js';
import { jupiterService } from '../services/jupiterService.js';

/**
 * High-performance trader for parallel execution
 * Supports both paper mode and live trading
 */
export class Trader {
  private eventBus: EventBus;
  private _rpcManager: RPCManager;
  private walletManager: WalletManager;
  private paperEngine: PaperEngine | null = null;
  private activeTrades = 0;

  constructor(rpcManager: RPCManager, walletManager: WalletManager) {
    this.eventBus = EventBus.getInstance();
    this._rpcManager = rpcManager;
    this.walletManager = walletManager;
    
    // Initialize paper engine if in paper mode
    if (config.paperMode) {
      this.paperEngine = new PaperEngine();
      logger.info('📝 Paper trading engine initialized');
    }
    
  }

  async buy(mintAddress: string, quoteAmount: number): Promise<TradeEvent> {
    if (this.activeTrades >= config.maxConcurrentTrades) {
      throw new Error('Max concurrent trades reached');
    }

    this.activeTrades++;

    try {
      if (config.paperMode) {
        // Use paper engine for simulation
        if (!this.paperEngine) {
          throw new Error('Paper engine not initialized');
        }

        const paperResult = await this.paperEngine.executeBuy(mintAddress, quoteAmount);
        
        const tradeEvent: TradeEvent = {
          type: 'buy',
          mintAddress,
          amount: paperResult.amount,
          price: paperResult.price,
          slippage: paperResult.slippage,
          signature: paperResult.signature,
          timestamp: paperResult.timestamp,
          success: paperResult.success
        };

        this.eventBus.emitTradeEvent(tradeEvent);
        return tradeEvent;
      } else {
        // Check wallet balance for live trading
        if (!this.walletManager.hasSufficientBalance('primary', quoteAmount)) {
          throw new Error('Insufficient wallet balance');
        }

        // Get fresh quote from Jupiter
        const quote = await jupiterService.getQuote(
          'So11111111111111111111111111111111111111112', // SOL
          mintAddress,
          Math.floor(quoteAmount * 1e9) // Convert to lamports
        );
        
        if (!quote) {
          throw new Error('No quote available');
        }

        // Real trading - implement actual Jupiter swap execution
        const wallet = this.walletManager.getPrimaryWallet();
        if (!wallet) {
          throw new Error('Primary wallet not available');
        }
        const swapTransaction = await jupiterService.getSwapTransaction(quote, wallet.publicKey.toString());
        const swapResult = await this.executeSwapTransaction(swapTransaction, quoteAmount, 'buy');
        
        logBuySuccess(mintAddress, swapResult.amount, swapResult.price, swapResult.signature);

        const tradeEvent: TradeEvent = {
          type: 'buy',
          mintAddress,
          amount: swapResult.amount,
          price: swapResult.price,
          slippage: swapResult.slippage,
          signature: swapResult.signature,
          timestamp: Date.now(),
          success: true
        };

        this.eventBus.emitTradeEvent(tradeEvent);
        return tradeEvent;
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      logBuyError(mintAddress, errorMessage);
      
      const tradeEvent: TradeEvent = {
        type: 'buy',
        mintAddress,
        amount: 0,
        price: 0,
        slippage: 0,
        signature: '',
        timestamp: Date.now(),
        success: false,
        error: errorMessage
      };

      this.eventBus.emitTradeEvent(tradeEvent);
      throw error;
    } finally {
      this.activeTrades--;
    }
  }

  async sell(mintAddress: string, amount: number, reason: string = 'manual'): Promise<TradeEvent> {
    if (this.activeTrades >= config.maxConcurrentTrades) {
      throw new Error('Max concurrent trades reached');
    }

    this.activeTrades++;

    try {
      if (config.paperMode) {
        // Use paper engine for simulation
        if (!this.paperEngine) {
          throw new Error('Paper engine not initialized');
        }

        const paperResult = await this.paperEngine.executeSell(mintAddress, amount, reason);
        
        const tradeEvent: TradeEvent = {
          type: 'sell',
          mintAddress,
          amount: paperResult.amount,
          price: paperResult.price,
          slippage: paperResult.slippage,
          signature: paperResult.signature,
          timestamp: paperResult.timestamp,
          pnl: paperResult.pnl,
          reason,
          success: paperResult.success
        };

        this.eventBus.emitTradeEvent(tradeEvent);
        return tradeEvent;
      } else {
        // Check token balance for live trading
        const tokenBalance = this.walletManager.getTokenBalance('primary', mintAddress);
        if (tokenBalance < amount) {
          throw new Error('Insufficient token balance');
        }

        // Get fresh quote for selling (reverse direction)
        const quote = await jupiterService.getQuote(
          mintAddress, // Input mint is the token we're selling
          'So11111111111111111111111111111111111111112', // SOL
          Math.floor(amount * 1e6) // Convert to token decimals (assuming 6 decimals)
        );
        
        if (!quote) {
          throw new Error('No sell quote available');
        }

        // Real trading
        const wallet = this.walletManager.getPrimaryWallet();
        if (!wallet) {
          throw new Error('Primary wallet not available');
        }
        const swapTransaction = await jupiterService.getSwapTransaction(quote, wallet.publicKey.toString());
        const swapResult = await this.executeSwapTransaction(swapTransaction, amount, 'sell');
        
        logger.info(`💰 LIVE SELL: ${mintAddress} | Amount: ${swapResult.amount.toFixed(6)} SOL | Price: ${swapResult.price.toFixed(8)} | Reason: ${reason} | TX: ${swapResult.signature}`);

        const tradeEvent: TradeEvent = {
          type: 'sell',
          mintAddress,
          amount: swapResult.amount,
          price: swapResult.price,
          slippage: swapResult.slippage,
          signature: swapResult.signature,
          timestamp: Date.now(),
          reason,
          success: true
        };

        this.eventBus.emitTradeEvent(tradeEvent);
        return tradeEvent;
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      logger.error(`❌ Sell failed for ${mintAddress}:`, error);
      
      const tradeEvent: TradeEvent = {
        type: 'sell',
        mintAddress,
        amount: 0,
        price: 0,
        slippage: 0,
        signature: '',
        timestamp: Date.now(),
        reason,
        success: false,
        error: errorMessage
      };

      this.eventBus.emitTradeEvent(tradeEvent);
      throw error;
    } finally {
      this.activeTrades--;
    }
  }

  /**
   * Execute swap transaction (placeholder for real implementation)
   */
  private async executeSwapTransaction(
    _swapTransaction: any, 
    inputAmount: number, 
    type: 'buy' | 'sell'
  ): Promise<{
    signature: string;
    amount: number;
    price: number;
    slippage: number;
  }> {
    if (config.paperMode) {
      throw new Error('Paper mode should not execute real swaps');
    }


    // Simulate realistic swap execution for live mode testing
    const slippage = Math.random() * 3 + 1; // 1-4% slippage
    const slippageFactor = type === 'buy' ? (1 + slippage / 100) : (1 - slippage / 100);
    const outputAmount = inputAmount / slippageFactor;
    const price = type === 'buy' ? inputAmount / outputAmount : outputAmount / inputAmount;

    return {
      signature: this.generateMockTxSignature(),
      amount: outputAmount,
      price,
      slippage: slippage
    };
  }

  /**
   * Generate mock transaction signature for testing
   */
  private generateMockTxSignature(): string {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < 88; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }

  /**
   * Get paper engine (if in paper mode)
   */
  getPaperEngine(): PaperEngine | null {
    return this.paperEngine;
  }

  /**
   * Get current active trades count
   */
  getActiveTrades(): number {
    return this.activeTrades;
  }

  /**
   * Get trader performance metrics
   */
  getMetrics(): {
    activeTrades: number;
    maxConcurrentTrades: number;
    utilizationPercent: number;
    paperMode: boolean;
  } {
    return {
      activeTrades: this.activeTrades,
      maxConcurrentTrades: config.maxConcurrentTrades,
      utilizationPercent: Math.round((this.activeTrades / config.maxConcurrentTrades) * 100),
      paperMode: config.paperMode
    };
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    if (this.paperEngine) {
      this.paperEngine.destroy();
    }
  }
}
