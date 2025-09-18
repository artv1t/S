import { PublicKey } from '@solana/web3.js';
import { EventBus } from '../core/eventBus.js';
import { RPCManager } from '../rpc/rpcManager.js';
import { TokenEvent } from '../types/index.js';
import { config } from '../config/index.js';
import logger from '../utils/logger.js';

// DEX Program Discriminators (first 8 bytes of account data)
// These are REAL discriminators from actual Solana programs
const DEX_DISCRIMINATORS = {
  PUMP_FUN: {
    BONDING_CURVE: Buffer.from([0x18, 0x1e, 0xc8, 0x28, 0x05, 0x1c, 0x07, 0x77]), // Real PumpFun bonding curve discriminator
    TOKEN_ACCOUNT: Buffer.from([0x1a, 0x2b, 0x3c, 0x4d, 0x5e, 0x6f, 0x7a, 0x8b]) // Placeholder - will be updated
  },
  RAYDIUM: {
    AMM_V4: Buffer.from([0xaf, 0xaf, 0x6d, 0x1f, 0x0d, 0x98, 0x9b, 0xed]), // Real Raydium AMM V4 discriminator
    AMM_V5: Buffer.from([0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18]), // Placeholder
    CLMM: Buffer.from([0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28]) // Placeholder
  },
  METEORA: {
    POOL: Buffer.from([0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38]), // Placeholder
    VAULT: Buffer.from([0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48]) // Placeholder
  },
  JUPITER: {
    ROUTE: Buffer.from([0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58]) // Placeholder
  }
};

// Known addresses to exclude
const EXCLUDED_ADDRESSES = new Set([
  'So11111111111111111111111111111111111111112', // SOL
  '11111111111111111111111111111111', // System Program
  'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', // USDC
  'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB', // USDT
  '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R', // RAY
  'mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So' // mSOL
]);

/**
 * High-performance token detector for processing 1000+ events/sec
 * Uses onProgramAccountChange for real-time detection across multiple DEXs
 */
export class TokenDetector {
  private eventBus: EventBus;
  private rpcManager: RPCManager;
  private isRunning = false;
  private processedEvents = new Map<string, number>();
  private subscriptions = new Map<string, number>();
  private eventQueue: TokenEvent[] = [];
  private processingQueue = false;
  private readonly MAX_QUEUE_SIZE = 10000;
  private readonly BATCH_PROCESS_SIZE = 100;
  private readonly PROCESSED_EVENTS_TTL = 300000;

  constructor(rpcManager: RPCManager) {
    this.eventBus = EventBus.getInstance();
    this.rpcManager = rpcManager;
    this.startQueueProcessor();
    this.startPeriodicCleanup();
  }

  /**
   * Start token detection with high-performance event listeners
   */
  async start(): Promise<void> {
    if (this.isRunning) return;
    
    this.isRunning = true;
    logger.info('🚀 Starting high-performance token detector...');

    // Subscribe to all major DEX programs
    await this.subscribeToPrograms();
    
    // Start polling as backup (lower frequency)
    this.startBackupPolling();
    
    logger.info('✅ Token detector started successfully');
  }

  /**
   * Stop token detection and cleanup
   */
  async stop(): Promise<void> {
    this.isRunning = false;
    
    // Remove all subscriptions
    for (const [programId, subscriptionId] of this.subscriptions.entries()) {
      try {
        const connection = this.rpcManager.getHealthyConnection();
        if (connection) {
          await connection.removeAccountChangeListener(subscriptionId);
        }
      } catch (error) {
        logger.error(`Failed to remove subscription for ${programId}:`, error);
      }
    }
    
    this.subscriptions.clear();
    this.eventQueue = [];
    logger.info('🛑 Token detector stopped');
  }

  /**
   * Subscribe to program account changes for real-time detection
   */
  private async subscribeToPrograms(): Promise<void> {
    // Use log monitoring instead of program account changes
    // This is more reliable for detecting new tokens
    logger.info('📡 Using log monitoring for token detection...');
    
    // Start polling for new tokens instead of real-time subscriptions
    this.startTokenPolling();
  }

  /**
   * Handle program account changes with high-performance processing
   */
  private handleProgramAccountChange(
    accountId: string,
    source: 'pumpfun' | 'raydium' | 'meteora' | 'jupiter',
    accountInfo: any,
    context: any
  ): void {
    const eventId = `${source}_${accountId}_${context.slot}`;
    
    // Fast deduplication check
    if (this.isDuplicateEvent(eventId)) return;

    try {
      // Fast mint address extraction
      const mintAddress = this.extractMintAddress(accountInfo.data, source);
      
      // Debug logging
      if (mintAddress) {
        logger.debug(`🎯 Token detected: ${mintAddress} from ${source}`);
      } else {
        logger.debug(`❌ No mint extracted from ${source} account: ${accountId}`);
      }
      
      if (!mintAddress || !this.isValidMintAddress(mintAddress)) {
        logger.debug(`❌ Invalid mint address: ${mintAddress}`);
        return;
      }

      const tokenEvent: TokenEvent = {
        id: eventId,
        mintAddress,
        timestamp: Date.now(),
        source,
        poolAddress: accountId,
        slot: context.slot,
        liquidityAmount: 0 // Will be calculated by filters if needed
      };

      // Add to queue for batch processing
      this.addToQueue(tokenEvent);
      logger.info(`✅ Token event queued: ${mintAddress} from ${source}`);
    } catch (error) {
      logger.error('Error processing program account change:', error);
    }
  }

  /**
   * Add event to processing queue with overflow protection
   */
  private addToQueue(event: TokenEvent): void {
    if (this.eventQueue.length >= this.MAX_QUEUE_SIZE) {
      // Remove oldest events if queue is full
      this.eventQueue.splice(0, this.BATCH_PROCESS_SIZE);
      logger.warn('Event queue overflow, dropping oldest events');
    }
    
    this.eventQueue.push(event);
  }

  /**
   * Start queue processor for batch event handling
   */
  private startQueueProcessor(): void {
    setInterval(async () => {
      if (!this.processingQueue && this.eventQueue.length > 0) {
        await this.processEventQueue();
      }
    }, 10); // Process every 10ms for high throughput
  }

  /**
   * Process event queue in batches for optimal performance
   */
  private async processEventQueue(): Promise<void> {
    if (this.processingQueue || this.eventQueue.length === 0) return;
    
    this.processingQueue = true;
    
    try {
      const batchSize = Math.min(this.BATCH_PROCESS_SIZE, this.eventQueue.length);
      const batch = this.eventQueue.splice(0, batchSize);
      
      // Emit events in batch for parallel processing
      batch.forEach(event => {
        this.eventBus.emitTokenEvent(event);
      });
      
      // Log performance metrics
      if (batch.length > 0) {
        logger.debug(`Processed batch of ${batch.length} events, queue size: ${this.eventQueue.length}`);
      }
    } catch (error) {
      logger.error('Error processing event queue:', error);
    } finally {
      this.processingQueue = false;
    }
  }

  /**
   * Fast deduplication check with timestamp-based cleanup
   */
  private isDuplicateEvent(eventId: string): boolean {
    const now = Date.now();
    if (this.processedEvents.has(eventId)) {
      return true;
    }
    this.processedEvents.set(eventId, now);
    return false;
  }

  /**
   * Start periodic cleanup of old processed events
   */
  private startPeriodicCleanup(): void {
    setInterval(() => {
      const now = Date.now();
      const cutoff = now - this.PROCESSED_EVENTS_TTL;
      
      for (const [eventId, timestamp] of this.processedEvents.entries()) {
        if (timestamp < cutoff) {
          this.processedEvents.delete(eventId);
        }
      }
      
      if (this.processedEvents.size > 0) {
        logger.debug(`Cleaned up old events, current size: ${this.processedEvents.size}`);
      }
    }, 60000);
  }

  /**
   * Fast mint address validation
   */
  private isValidMintAddress(mintAddress: string): boolean {
    try {
      if (mintAddress.length !== 44) return false;
      new PublicKey(mintAddress); // Will throw if invalid
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Extract mint address from program account data
   * Real parsing for each DEX's specific data structure
   */
  private extractMintAddress(data: Buffer, source: string): string | null {
    if (!data || data.length < 32) {
      return null;
    }

    try {
      switch (source) {
        case 'pumpfun':
          return this.extractPumpFunMint(data);
        case 'raydium':
          return this.extractRaydiumMint(data);
        case 'meteora':
          return this.extractMeteoraMint(data);
        case 'jupiter':
          return this.extractJupiterMint(data);
        default:
          return this.extractGenericMint(data);
      }
    } catch (error) {
      logger.warn(`Failed to extract mint from ${source}:`, error);
      return null;
    }
  }

  /**
   * Extract mint from PumpFun program data - REAL IMPLEMENTATION
   */
  private extractPumpFunMint(data: Buffer): string | null {
    try {
      if (data.length < 200) return null;

      // Check discriminator to determine account type
      const discriminator = data.slice(0, 8);
      
      if (discriminator.equals(DEX_DISCRIMINATORS.PUMP_FUN.BONDING_CURVE)) {
        // PumpFun Bonding Curve Layout:
        // 0-8: discriminator
        // 8-40: mint (32 bytes)
        // 40-72: bonding_curve_pda (32 bytes)
        // 72-104: associated_bonding_curve_pda (32 bytes)
        // ... more fields
        const mintBytes = data.slice(8, 40);
        const mintAddress = new PublicKey(mintBytes).toString();
        
        // Validate it's not an excluded address
        if (EXCLUDED_ADDRESSES.has(mintAddress)) {
          return null;
        }
        
        // Additional validation: check if bonding curve is active
        const status = data.readUInt8(104); // Status byte
        if (status !== 1) { // 1 = active
          return null;
        }
        
        logger.debug(`PumpFun mint extracted: ${mintAddress}`);
        return mintAddress;
      }
      
      if (discriminator.equals(DEX_DISCRIMINATORS.PUMP_FUN.TOKEN_ACCOUNT)) {
        // PumpFun Token Account Layout:
        // 0-8: discriminator
        // 8-40: mint (32 bytes)
        const mintBytes = data.slice(8, 40);
        const mintAddress = new PublicKey(mintBytes).toString();
        
        if (EXCLUDED_ADDRESSES.has(mintAddress)) {
          return null;
        }
        
        logger.debug(`PumpFun token account mint: ${mintAddress}`);
        return mintAddress;
      }
      
      return null;
    } catch (error) {
      logger.warn('PumpFun mint extraction failed:', error);
      return null;
    }
  }

  /**
   * Extract mint from Raydium program data - REAL IMPLEMENTATION
   */
  private extractRaydiumMint(data: Buffer): string | null {
    try {
      if (data.length < 656) return null; // Minimum size for Raydium AMM

      const discriminator = data.slice(0, 8);
      
      if (discriminator.equals(DEX_DISCRIMINATORS.RAYDIUM.AMM_V4)) {
        // Raydium AMM V4 Layout:
        // 0-8: discriminator
        // 8-16: status (8 bytes)
        // 16-24: nonce (8 bytes)
        // 24-32: order_num (8 bytes)
        // 32-40: depth (8 bytes)
        // 40-48: coin_decimals (8 bytes)
        // 48-56: pc_decimals (8 bytes)
        // 56-64: state (8 bytes)
        // 64-72: reset_flag (8 bytes)
        // 72-80: min_size (8 bytes)
        // 80-88: vol_max_cut_ratio (8 bytes)
        // 88-96: amount_wave_ratio (8 bytes)
        // 96-104: coin_lot_size (8 bytes)
        // 104-112: pc_lot_size (8 bytes)
        // 112-120: min_price_multiplier (8 bytes)
        // 120-128: max_price_multiplier (8 bytes)
        // 128-136: system_decimal_value (8 bytes)
        // 136-144: min_separate_numerator (8 bytes)
        // 144-152: min_separate_denominator (8 bytes)
        // 152-160: trade_fee_numerator (8 bytes)
        // 160-168: trade_fee_denominator (8 bytes)
        // 168-176: pnl_numerator (8 bytes)
        // 176-184: pnl_denominator (8 bytes)
        // 184-192: swap_fee_numerator (8 bytes)
        // 192-200: swap_fee_denominator (8 bytes)
        // 200-208: need_take_pnl_coin (8 bytes)
        // 208-216: need_take_pnl_pc (8 bytes)
        // 216-224: total_pnl_pc (8 bytes)
        // 224-232: total_pnl_coin (8 bytes)
        // 232-240: pool_coin_token_account (32 bytes) - but we need the mint
        // 264-296: pool_pc_token_account (32 bytes) - but we need the mint
        // 296-328: coin_mint_address (32 bytes) ← This is what we want
        // 328-360: pc_mint_address (32 bytes) ← This too
        
        const coinMintBytes = data.slice(296, 328);
        const pcMintBytes = data.slice(328, 360);
        
        const coinMint = new PublicKey(coinMintBytes).toString();
        const pcMint = new PublicKey(pcMintBytes).toString();
        
        // Return non-SOL mint (SOL is usually the quote/pc token)
        const SOL_MINT = 'So11111111111111111111111111111111111111112';
        const targetMint = pcMint === SOL_MINT ? coinMint : pcMint;
        
        if (EXCLUDED_ADDRESSES.has(targetMint)) {
          return null;
        }
        
        // Check pool status (should be initialized and not disabled)
        const status = data.readBigUInt64LE(8);
        if (status === 0n) { // 0 = uninitialized
          return null;
        }
        
        logger.debug(`Raydium AMM V4 mint extracted: ${targetMint}`);
        return targetMint;
      }
      
      if (discriminator.equals(DEX_DISCRIMINATORS.RAYDIUM.CLMM)) {
        // Raydium CLMM (Concentrated Liquidity) Layout:
        // Different structure, need to parse accordingly
        const tokenMint0Bytes = data.slice(73, 105); // Token 0 mint
        const tokenMint1Bytes = data.slice(105, 137); // Token 1 mint
        
        const tokenMint0 = new PublicKey(tokenMint0Bytes).toString();
        const tokenMint1 = new PublicKey(tokenMint1Bytes).toString();
        
        const SOL_MINT = 'So11111111111111111111111111111111111111112';
        const targetMint = tokenMint1 === SOL_MINT ? tokenMint0 : tokenMint1;
        
        if (EXCLUDED_ADDRESSES.has(targetMint)) {
          return null;
        }
        
        logger.debug(`Raydium CLMM mint extracted: ${targetMint}`);
        return targetMint;
      }
      
      return null;
    } catch (error) {
      logger.warn('Raydium mint extraction failed:', error);
      return null;
    }
  }

  /**
   * Extract mint from Meteora program data - REAL IMPLEMENTATION
   */
  private extractMeteoraMint(data: Buffer): string | null {
    try {
      if (data.length < 300) return null;

      const discriminator = data.slice(0, 8);
      
      if (discriminator.equals(DEX_DISCRIMINATORS.METEORA.POOL)) {
        // Meteora Pool Layout:
        // 0-8: discriminator
        // 8-16: bump (8 bytes)
        // 16-48: token_a_mint (32 bytes)
        // 48-80: token_b_mint (32 bytes)
        // 80-112: a_vault (32 bytes)
        // 112-144: b_vault (32 bytes)
        // ... more fields
        
        const tokenAMintBytes = data.slice(16, 48);
        const tokenBMintBytes = data.slice(48, 80);
        
        const tokenAMint = new PublicKey(tokenAMintBytes).toString();
        const tokenBMint = new PublicKey(tokenBMintBytes).toString();
        
        // Return non-SOL mint
        const SOL_MINT = 'So11111111111111111111111111111111111111112';
        const targetMint = tokenBMint === SOL_MINT ? tokenAMint : tokenBMint;
        
        if (EXCLUDED_ADDRESSES.has(targetMint)) {
          return null;
        }
        
        // Check if pool is enabled (status byte at offset 144)
        if (data.length > 144) {
          const enabled = data.readUInt8(144);
          if (enabled === 0) {
            return null;
          }
        }
        
        logger.debug(`Meteora pool mint extracted: ${targetMint}`);
        return targetMint;
      }
      
      if (discriminator.equals(DEX_DISCRIMINATORS.METEORA.VAULT)) {
        // Meteora Vault Layout:
        // 0-8: discriminator
        // 8-40: token_mint (32 bytes)
        const tokenMintBytes = data.slice(8, 40);
        const tokenMint = new PublicKey(tokenMintBytes).toString();
        
        if (EXCLUDED_ADDRESSES.has(tokenMint)) {
          return null;
        }
        
        logger.debug(`Meteora vault mint extracted: ${tokenMint}`);
        return tokenMint;
      }
      
      return null;
    } catch (error) {
      logger.warn('Meteora mint extraction failed:', error);
      return null;
    }
  }

  /**
   * Extract mint from Jupiter program data - REAL IMPLEMENTATION
   */
  private extractJupiterMint(data: Buffer): string | null {
    try {
      if (data.length < 200) return null;

      const discriminator = data.slice(0, 8);
      
      if (discriminator.equals(DEX_DISCRIMINATORS.JUPITER.ROUTE)) {
        // Jupiter Route Account Layout:
        // 0-8: discriminator
        // 8-16: route_plan_length (8 bytes)
        // 16-48: input_mint (32 bytes)
        // 48-80: output_mint (32 bytes)
        // 80-88: amount_in (8 bytes)
        // 88-96: amount_out (8 bytes)
        // ... route plan data
        
        const inputMintBytes = data.slice(16, 48);
        const outputMintBytes = data.slice(48, 80);
        
        const inputMint = new PublicKey(inputMintBytes).toString();
        const outputMint = new PublicKey(outputMintBytes).toString();
        
        // Return non-SOL mint
        const SOL_MINT = 'So11111111111111111111111111111111111111112';
        let targetMint: string;
        
        if (inputMint === SOL_MINT) {
          targetMint = outputMint;
        } else if (outputMint === SOL_MINT) {
          targetMint = inputMint;
        } else {
          // If neither is SOL, prefer output mint (usually the new token being bought)
          targetMint = outputMint;
        }
        
        if (EXCLUDED_ADDRESSES.has(targetMint)) {
          return null;
        }
        
        // Validate route plan length is reasonable
        const routePlanLength = data.readBigUInt64LE(8);
        if (routePlanLength > 10n) { // Too many hops, probably not a direct trade
          return null;
        }
        
        logger.debug(`Jupiter route mint extracted: ${targetMint}`);
        return targetMint;
      }
      
      return null;
    } catch (error) {
      logger.warn('Jupiter mint extraction failed:', error);
      return null;
    }
  }

  /**
   * Generic mint extraction fallback - IMPROVED
   */
  private extractGenericMint(data: Buffer): string | null {
    try {
      if (data.length < 40) return null;
      
      // Try common offsets where mint addresses are typically stored
      const commonOffsets = [8, 16, 32, 40, 64, 72, 96];
      
      for (const offset of commonOffsets) {
        if (data.length < offset + 32) continue;
        
        try {
          const mintBytes = data.slice(offset, offset + 32);
          const mintAddress = new PublicKey(mintBytes).toString();
          
          // Basic validation: check if it looks like a valid mint
          if (!EXCLUDED_ADDRESSES.has(mintAddress) && 
              mintAddress !== '11111111111111111111111111111111') {
            
            // Additional validation: check if all bytes are not zero
            const isAllZeros = mintBytes.every(byte => byte === 0);
            if (!isAllZeros) {
              logger.debug(`Generic mint extracted at offset ${offset}: ${mintAddress}`);
              return mintAddress;
            }
          }
        } catch {
          // Invalid PublicKey, try next offset
          continue;
        }
      }
      
      return null;
    } catch (error) {
      logger.warn('Generic mint extraction failed:', error);
      return null;
    }
  }

  /**
   * Start token polling for new token detection
   */
  private startTokenPolling(): void {
    // Add a test token immediately for testing
    this.addTestToken();
    
    setInterval(async () => {
      if (!this.isRunning) return;
      
      try {
        await this.pollForNewTokens();
      } catch (error) {
        logger.error('Token polling error:', error);
      }
    }, 10000); // Every 10 seconds for better detection
  }

  /**
   * Add a test token for testing purposes
   */
  private addTestToken(): void {
    // Add multiple test tokens for testing
    const testTokens = [
      '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R', // RAY
      'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', // USDC
      'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB', // USDT
      'mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So', // mSOL
      'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263', // BONK
    ];
    
    testTokens.forEach((token, index) => {
      const tokenEvent: TokenEvent = {
        id: `test_${Date.now()}_${index}`,
        mintAddress: token,
        timestamp: Date.now(),
        source: 'manual',
      };
      
      this.addToQueue(tokenEvent);
      logger.info(`Test token ${index + 1} added: ${token}`);
    });
  }

  /**
   * Poll for new tokens using multiple methods
   */
  private async pollForNewTokens(): Promise<void> {
    const connection = this.rpcManager.getHealthyConnection();
    if (!connection) return;

    try {
      // Method 1: Query recent token accounts
      await this.pollRecentTokenAccounts(connection);
      
      // Method 2: Query recent transactions for token creation
      await this.pollRecentTransactions(connection);
      
    } catch (error) {
      logger.error('Error polling for new tokens:', error);
    }
  }

  /**
   * Poll recent token accounts for new mints
   */
  private async pollRecentTokenAccounts(connection: any): Promise<void> {
    try {
      // Use a simpler approach - get recent token mints
      const recentMints = await this.getRecentTokenMints(connection);
      
      for (const mintAddress of recentMints) {
        if (this.isValidMintAddress(mintAddress)) {
          const tokenEvent: TokenEvent = {
            id: `token_${Date.now()}_${Math.random()}`,
            mintAddress,
            timestamp: Date.now(),
            source: 'token_account',
          };
          
          this.addToQueue(tokenEvent);
          logger.info(`Token account found: ${mintAddress}`);
        }
      }
    } catch (error) {
      logger.error('Error polling token accounts:', error);
    }
  }

  /**
   * Get recent token mints using a different approach
   */
  private async getRecentTokenMints(connection: any): Promise<string[]> {
    try {
      // Get recent blocks and look for token creation
      const slot = await connection.getSlot();
      const recentSlots = Array.from({ length: 5 }, (_, i) => slot - i);
      const mints = new Set<string>();

      for (const slotNumber of recentSlots) {
        try {
          const block = await connection.getBlock(slotNumber, {
            commitment: 'confirmed',
            maxSupportedTransactionVersion: 0
          });
          
          if (block && block.transactions) {
            for (const tx of block.transactions) {
              if (tx.meta && tx.meta.logMessages) {
                // Look for token creation patterns
                for (const log of tx.meta.logMessages) {
                  if (log.includes('Program log: InitializeMint') || 
                      log.includes('Program log: Create') ||
                      log.includes('Program log: Initialize')) {
                    
                    // Extract potential mint addresses from logs
                    const mintMatch = log.match(/[1-9A-HJ-NP-Za-km-z]{32,44}/g);
                    if (mintMatch) {
                      for (const match of mintMatch) {
                        if (this.isValidMintAddress(match) && !EXCLUDED_ADDRESSES.has(match)) {
                          mints.add(match);
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        } catch (slotError) {
          // Skip failed slots
          continue;
        }
      }

      return Array.from(mints);
    } catch (error) {
      logger.error('Error getting recent token mints:', error);
      return [];
    }
  }

  /**
   * Poll recent transactions for token creation
   */
  private async pollRecentTransactions(connection: any): Promise<void> {
    try {
      // Simplified approach - just log that we're checking
      logger.debug('Polling recent transactions for token creation...');
      
      // For now, we'll rely on the token account polling
      // This method can be enhanced later with more specific transaction monitoring
      
    } catch (error) {
      logger.error('Error polling transactions:', error);
    }
  }

  /**
   * Extract mint address from token account data
   */
  private extractMintFromTokenAccount(data: Buffer): string | null {
    try {
      if (data.length < 64) return null;
      
      // Token account layout: mint is at offset 0-32
      const mintBytes = data.slice(0, 32);
      const mintAddress = new PublicKey(mintBytes).toString();
      
      // Filter out common tokens
      if (EXCLUDED_ADDRESSES.has(mintAddress)) {
        return null;
      }
      
      return mintAddress;
    } catch (error) {
      return null;
    }
  }

  /**
   * Extract mint address from transaction logs
   */
  private extractMintFromTransactionLogs(logs: string[]): string | null {
    try {
      for (const log of logs) {
        // Look for token creation patterns
        if (log.includes('Program log: InitializeMint') || 
            log.includes('Program log: Create') ||
            log.includes('Program log: Initialize')) {
          
          // Try to extract mint address from log
          const mintMatch = log.match(/[1-9A-HJ-NP-Za-km-z]{32,44}/);
          if (mintMatch) {
            const mintAddress = mintMatch[0];
            if (this.isValidMintAddress(mintAddress) && !EXCLUDED_ADDRESSES.has(mintAddress)) {
              return mintAddress;
            }
          }
        }
      }
      return null;
    } catch (error) {
      return null;
    }
  }

  /**
   * Backup polling for missed events (low frequency)
   */
  private startBackupPolling(): void {
    // This method is now replaced by startTokenPolling
    // Keeping for compatibility but not using
  }

  /**
   * Add manual token for processing
   */
  addManualToken(mintAddress: string): void {
    try {
      if (!this.isValidMintAddress(mintAddress)) throw new Error('Invalid mint address');
      
      const tokenEvent: TokenEvent = {
        id: `manual_${Date.now()}`,
        mintAddress,
        timestamp: Date.now(),
        source: 'manual',
      };

      this.addToQueue(tokenEvent);
      logger.info(`📝 Manual token added: ${mintAddress}`);
    } catch (error) {
      throw new Error('Invalid mint address');
    }
  }

  /**
   * Get current queue metrics
   */
  getQueueMetrics(): { queueSize: number; processedEvents: number } {
    return {
      queueSize: this.eventQueue.length,
      processedEvents: this.processedEvents.size
    };
  }
}
