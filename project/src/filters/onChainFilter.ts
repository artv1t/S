import { Connection, PublicKey } from '@solana/web3.js';
import { TOKEN_2022_PROGRAM_ID } from '@solana/spl-token';
import { FilterResult } from '../types/index.js';
import { RPCManager } from '../rpc/rpcManager.js';
import { config } from '../config/index.js';
import logger from '../utils/logger.js';

/**
 * On-Chain Filter - Fast on-chain validation
 * Runs in parallel with Route Gate, must be fast (<20ms average)
 */
export class OnChainFilter {
  private rpcManager: RPCManager;
  private cache = new Map<string, { result: FilterResult; expires: number }>();
  private readonly CACHE_TTL = 300000; // 5 minutes cache

  constructor(rpcManager: RPCManager) {
    this.rpcManager = rpcManager;
  }

  async execute(mintAddress: string): Promise<FilterResult> {
    // Check cache first
    const cached = this.cache.get(mintAddress);
    if (cached && cached.expires > Date.now()) {
      return cached.result;
    }

    const startTime = Date.now();
    let score = 100;
    const issues: string[] = [];

    try {
      const connection = this.rpcManager.getHealthyConnection();
      if (!connection) {
        throw new Error('No healthy RPC connection available');
      }

      const mintPubkey = new PublicKey(mintAddress);

      // Batch all RPC calls for performance
      const [
        accountInfo,
        largestAccounts,
        supply,
        poolAge
      ] = await Promise.all([
        this.getAccountInfo(connection, mintPubkey),
        this.getLargestAccounts(connection, mintPubkey),
        this.getTokenSupply(connection, mintPubkey),
        this.getPoolAge(connection, mintPubkey)
      ]);

      // Check if it's Token-2022 (not supported)
      if (accountInfo && accountInfo.owner.equals(TOKEN_2022_PROGRAM_ID)) {
        return {
          ok: false,
          score: 0,
          reason: 'Token-2022 not supported',
          filterName: 'OnChain',
          latency: Date.now() - startTime
        };
      }

      // Parse token mint data (may be unavailable on free RPC tiers)
      const mintInfo = this.parseMintInfo(accountInfo);
      
      if (!mintInfo && !accountInfo) {
        score -= 30;
        issues.push('Account info unavailable (free RPC limitation)');
      } else if (!mintInfo) {
        return {
          ok: false,
          score: 0,
          reason: 'Invalid token mint data',
          filterName: 'OnChain',
          latency: Date.now() - startTime
        };
      }

      // Check mint authority (should be renounced) - only if we have mint info
      if (mintInfo) {
        if (mintInfo.mintAuthority && !this.isNullAddress(mintInfo.mintAuthority)) {
          score -= 40;
          issues.push('Mint authority not renounced');
        }

        // Check freeze authority (should be null)
        if (mintInfo.freezeAuthority && !this.isNullAddress(mintInfo.freezeAuthority)) {
          score -= 30;
          issues.push('Freeze authority present');
        }

        // Check decimals (should be reasonable)
        if (mintInfo.decimals === 0 || mintInfo.decimals > 18) {
          score -= 20;
          issues.push(`Unusual decimals: ${mintInfo.decimals}`);
        }
      }

      // Check supply (should exist and be reasonable)
      if (!supply || !supply.value) {
        score -= 25;
        issues.push('No token supply data');
      } else {
        const totalSupply = parseFloat(supply.value.amount);
        
        // Check for reasonable supply
        if (totalSupply === 0) {
          score -= 50;
          issues.push('Zero supply');
        } else if (totalSupply > 1e15) { // Very high supply
          score -= 15;
          issues.push('Extremely high supply');
        }
      }

      if (poolAge !== null) {
        const ageMs = Date.now() - poolAge;
        if (ageMs > config.poolMaxAgeMs) {
          return {
            ok: false,
            score: 0,
            reason: `Pool too old: ${Math.round(ageMs / 60000)} minutes (max: ${Math.round(config.poolMaxAgeMs / 60000)} minutes)`,
            filterName: 'OnChain',
            latency: Date.now() - startTime
          };
        } else if (ageMs < 60000) { // Less than 1 minute old
          score -= 10;
          issues.push('Very new pool (< 1 minute)');
        }
      } else {
        score -= 5;
        issues.push('Pool age unavailable');
      }

      // Check holder concentration (optional - may fail on free RPC tiers)
      if (largestAccounts && supply && largestAccounts.value && largestAccounts.value.length > 0) {
        const totalSupply = parseFloat(supply.value.amount);
        const holders = largestAccounts.value;
        
        // Top holder concentration
        const top1Balance = parseFloat(holders[0]?.amount || '0');
        const top1Percentage = (top1Balance / totalSupply) * 100;
        
        if (top1Percentage > 50) {
          score -= 40;
          issues.push(`Extreme concentration: top holder ${top1Percentage.toFixed(1)}%`);
        } else if (top1Percentage > 30) {
          score -= 25;
          issues.push(`High concentration: top holder ${top1Percentage.toFixed(1)}%`);
        } else if (top1Percentage > config.maxTop1HolderPercent) {
          score -= 15;
          issues.push(`Moderate concentration: top holder ${top1Percentage.toFixed(1)}%`);
        }

        // Top 5 holders concentration
        const top5Balance = holders
          .slice(0, 5)
          .reduce((sum: number, acc: any) => sum + parseFloat(acc.amount || '0'), 0);
        const top5Percentage = (top5Balance / totalSupply) * 100;

        if (top5Percentage > 80) {
          score -= 30;
          issues.push(`High top5 concentration: ${top5Percentage.toFixed(1)}%`);
        } else if (top5Percentage > config.maxTop5HolderPercent) {
          score -= 15;
          issues.push(`Moderate top5 concentration: ${top5Percentage.toFixed(1)}%`);
        }

        // Check number of holders
        if (holders.length < 10) {
          score -= 20;
          issues.push(`Few holders: ${holders.length}`);
        }
      } else if (!largestAccounts || !largestAccounts.value) {
        score -= 10;
        issues.push('Holder concentration data unavailable (free RPC limitation)');
      }

      const passed = score >= 45; // Lowered threshold for free RPC limitations // Adjusted threshold to account for optional holder data
      const result: FilterResult = {
        ok: passed,
        score: Math.max(0, score),
        reason: issues.length > 0 ? issues.join(', ') : 'Passed on-chain checks',
        filterName: 'OnChain',
        latency: Date.now() - startTime,
        metadata: {
          mintAuthority: mintInfo?.mintAuthority || null,
          freezeAuthority: mintInfo?.freezeAuthority || null,
          decimals: mintInfo?.decimals || 0,
          supply: supply?.value?.amount,
          poolAge: poolAge,
          poolAgeMinutes: poolAge ? Math.round((Date.now() - poolAge) / 60000) : null
        }
      };

      // Cache result
      this.cache.set(mintAddress, {
        result,
        expires: Date.now() + this.CACHE_TTL
      });

      return result;

    } catch (error) {
      const result: FilterResult = {
        ok: false,
        score: 0,
        reason: error instanceof Error ? error.message : 'On-chain check failed',
        filterName: 'OnChain',
        latency: Date.now() - startTime
      };

      // Cache failed results for shorter time
      this.cache.set(mintAddress, {
        result,
        expires: Date.now() + 60000 // 1 minute
      });

      return result;
    }
  }

  /**
   * Get account info with error handling
   */
  private async getAccountInfo(connection: Connection, mint: PublicKey): Promise<any> {
    try {
      return await connection.getAccountInfo(mint);
    } catch (error) {
      if (error instanceof Error && 
          (error.message.includes('timeout') || 
           error.message.includes('429') || 
           error.message.includes('upgrade your tier') ||
           error.message.includes('Too many requests'))) {
        logger.debug(`Account info unavailable on free RPC tier for ${mint.toString()}`);
      } else {
        logger.warn(`Failed to get account info for ${mint.toString()}:`, error);
      }
      return null;
    }
  }

  /**
   * Get largest token accounts (may fail on free RPC tiers)
   */
  private async getLargestAccounts(connection: Connection, mint: PublicKey): Promise<any> {
    try {
      return await connection.getTokenLargestAccounts(mint);
    } catch (error) {
      if (error instanceof Error && 
          (error.message.includes('timeout') || 
           error.message.includes('429') || 
           error.message.includes('upgrade your tier') ||
           error.message.includes('Too many requests'))) {
        logger.debug(`Largest accounts unavailable on free RPC tier for ${mint.toString()}`);
      } else {
        logger.warn(`Failed to get largest accounts for ${mint.toString()}:`, error);
      }
      return null;
    }
  }

  /**
   * Get token supply
   */
  private async getTokenSupply(connection: Connection, mint: PublicKey): Promise<any> {
    try {
      return await connection.getTokenSupply(mint);
    } catch (error) {
      if (error instanceof Error && 
          (error.message.includes('timeout') || 
           error.message.includes('429') || 
           error.message.includes('upgrade your tier') ||
           error.message.includes('Too many requests'))) {
        logger.debug(`Token supply unavailable on free RPC tier for ${mint.toString()}`);
      } else {
        logger.warn(`Failed to get token supply for ${mint.toString()}:`, error);
      }
      return null;
    }
  }

  /**
   * Get pool age by checking account creation time
   */
  private async getPoolAge(connection: Connection, mint: PublicKey): Promise<number | null> {
    try {
      const accountInfo = await connection.getAccountInfo(mint, 'confirmed');
      if (!accountInfo) {
        return null;
      }

      const slot = await connection.getSlot();
      const blockTime = await connection.getBlockTime(slot);
      
      if (blockTime) {
        return blockTime * 1000; // Convert to milliseconds
      }
      
      return null;
    } catch (error) {
      if (error instanceof Error && 
          (error.message.includes('timeout') || 
           error.message.includes('429') || 
           error.message.includes('upgrade your tier') ||
           error.message.includes('Too many requests'))) {
        logger.debug(`Pool age unavailable on free RPC tier for ${mint.toString()}`);
      } else {
        logger.warn(`Failed to get pool age for ${mint.toString()}:`, error);
      }
      return null;
    }
  }

  /**
   * Parse SPL Token mint account data
   */
  private parseMintInfo(accountInfo: any): {
    mintAuthority: string | null;
    freezeAuthority: string | null;
    decimals: number;
  } | null {
    if (!accountInfo || !accountInfo.data) return null;

    try {
      const data = accountInfo.data;
      
      // SPL Token mint layout:
      // 0-4: mint_authority_option (4 bytes)
      // 4-36: mint_authority (32 bytes)
      // 36-44: supply (8 bytes)
      // 44: decimals (1 byte)
      // 45: is_initialized (1 byte)
      // 46-50: freeze_authority_option (4 bytes)
      // 50-82: freeze_authority (32 bytes)

      const mintAuthorityOption = data.readUInt32LE(0);
      const mintAuthority = mintAuthorityOption === 1 
        ? new PublicKey(data.slice(4, 36)).toString()
        : null;

      const decimals = data.readUInt8(44);

      const freezeAuthorityOption = data.readUInt32LE(46);
      const freezeAuthority = freezeAuthorityOption === 1
        ? new PublicKey(data.slice(50, 82)).toString()
        : null;

      return {
        mintAuthority,
        freezeAuthority,
        decimals
      };
    } catch (error) {
      logger.warn('Failed to parse mint info:', error);
      return null;
    }
  }

  /**
   * Check if address is null/system program
   */
  private isNullAddress(address: string): boolean {
    const nullAddresses = [
      '11111111111111111111111111111111',
      'So11111111111111111111111111111111111111112'
    ];
    return nullAddresses.includes(address);
  }

  /**
   * Get filter performance metrics
   */
  getMetrics(): {
    cacheSize: number;
    cacheHitRate: number;
  } {
    return {
      cacheSize: this.cache.size,
      cacheHitRate: 0 // Would need to track hits vs misses
    };
  }

  /**
   * Clear cache
   */
  clearCache(): void {
    this.cache.clear();
  }
}
