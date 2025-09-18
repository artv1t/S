import axios from 'axios';
import { FilterResult, JupiterQuote } from '../types/index.js';
import { config } from '../config/index.js';

/**
 * Route Gate Filter - Jupiter API liquidity check
 * CRITICAL: This filter runs FIRST and must be fast (<10ms average)
 */
export class RouteGateFilter {
  private cache = new Map<string, { result: FilterResult; expires: number }>();
  private rateLimitWindow = new Map<number, number>();
  private readonly RATE_LIMIT = 50; // 50 requests per second
  private readonly CACHE_TTL = 60000; // 1 minute cache
  private readonly TIMEOUT = 3000; // 3 second timeout
  private readonly JUPITER_API_URL = 'https://quote-api.jup.ag/v6/quote';

  constructor() {
    this.startPeriodicCacheCleanup();
  }

  async execute(mintAddress: string): Promise<FilterResult> {
    // Check cache first for performance
    const cached = this.cache.get(mintAddress);
    if (cached && cached.expires > Date.now()) {
      return cached.result;
    }

    // Rate limiting check
    if (this.isRateLimited()) {
      return {
        ok: false,
        score: 0,
        reason: 'Rate limited - too many requests',
        filterName: 'RouteGate',
        latency: 0
      };
    }

    const startTime = Date.now();

    try {
      // Jupiter API quote request with optimized parameters
      const response = await axios.get(this.JUPITER_API_URL, {
        params: {
          inputMint: 'So11111111111111111111111111111111111111112', // SOL
          outputMint: mintAddress,
          amount: Math.floor(config.quoteAmount * 1e9), // Convert to lamports
          slippageBps: 1500, // 15% max slippage
          maxAccounts: 20,
          onlyDirectRoutes: true, // Faster routing
          asLegacyTransaction: false
        },
        timeout: this.TIMEOUT,
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'SolanaSniper/1.0'
        }
      });

      const quote: JupiterQuote = response.data;
      if (!quote || !quote.outAmount) {
        const result: FilterResult = {
          ok: false,
          score: 0,
          reason: 'No liquidity route available',
          filterName: 'RouteGate',
          latency: Date.now() - startTime
        };
        this.cacheResult(mintAddress, result, 30000); // Cache failures for 30s
        return result;
      }

      // Calculate price impact and score
      const priceImpactPct = parseFloat(quote.priceImpactPct || '0');
      const routeLength = quote.routePlan?.length || 0;
      
      // Scoring algorithm (0-100)
      let score = 100;
      
      // Price impact penalty (most important)
      if (priceImpactPct > 15) {
        score = 0; // Immediate fail for high price impact
      } else if (priceImpactPct > 10) {
        score -= 30;
      } else if (priceImpactPct > 5) {
        score -= 15;
      }
      
      // Route complexity penalty
      if (routeLength > 3) {
        score -= 20;
      } else if (routeLength > 2) {
        score -= 10;
      }
      
      // Minimum output amount check
      const outputAmount = parseFloat(quote.outAmount) / 1e9;
      if (outputAmount < config.quoteAmount * 0.5) { // Less than 50% of expected
        score -= 25;
      }

      const passed = score >= 70 && priceImpactPct <= config.maxPriceImpact;
      
      const result: FilterResult = {
        ok: passed,
        score: Math.max(0, score),
        reason: passed 
          ? `Good liquidity: ${priceImpactPct.toFixed(2)}% impact` 
          : `High price impact: ${priceImpactPct.toFixed(2)}%`,
        filterName: 'RouteGate',
        latency: Date.now() - startTime,
        metadata: {
          priceImpact: priceImpactPct,
          routeLength,
          outputAmount
        }
      };

      this.cacheResult(mintAddress, result);
      return result;

    } catch (error) {
      const result: FilterResult = {
        ok: false,
        score: 0,
        reason: this.getErrorReason(error),
        filterName: 'RouteGate',
        latency: Date.now() - startTime
      };
      
      // Cache failed results for shorter time
      this.cacheResult(mintAddress, result, 30000);
      return result;
    }
  }

  /**
   * Efficient sliding window rate limiting
   */
  private isRateLimited(): boolean {
    const now = Date.now();
    const currentSecond = Math.floor(now / 1000);
    
    for (const [timestamp] of this.rateLimitWindow.entries()) {
      if (timestamp < currentSecond - 1) {
        this.rateLimitWindow.delete(timestamp);
      }
    }
    
    const currentCount = this.rateLimitWindow.get(currentSecond) || 0;
    if (currentCount >= this.RATE_LIMIT) {
      return true;
    }
    
    this.rateLimitWindow.set(currentSecond, currentCount + 1);
    return false;
  }

  /**
   * Cache filter result with TTL
   */
  private cacheResult(mintAddress: string, result: FilterResult, ttl = this.CACHE_TTL): void {
    this.cache.set(mintAddress, {
      result,
      expires: Date.now() + ttl
    });
  }

  /**
   * Start periodic cache cleanup to prevent memory bloat
   */
  private startPeriodicCacheCleanup(): void {
    setInterval(() => {
      const now = Date.now();
      let cleanedCount = 0;
      
      for (const [key, value] of this.cache.entries()) {
        if (value.expires < now) {
          this.cache.delete(key);
          cleanedCount++;
        }
      }
      
      if (cleanedCount > 0) {
        console.debug(`RouteGateFilter: Cleaned ${cleanedCount} expired cache entries, current size: ${this.cache.size}`);
      }
    }, 30000); // Run every 30 seconds
  }

  /**
   * Get human-readable error reason
   */
  private getErrorReason(error: any): string {
    if (axios.isAxiosError(error)) {
      if (error.code === 'ECONNABORTED') {
        return 'Request timeout';
      }
      if (error.response?.status === 429) {
        return 'API rate limited';
      }
      if (error.response && error.response.status >= 500) {
        return 'Jupiter API error';
      }
      return `API error: ${error.response?.status || 'unknown'}`;
    }
    
    return error instanceof Error ? error.message : 'Unknown error';
  }

  /**
   * Get filter performance metrics
   */
  getMetrics(): {
    cacheSize: number;
    cacheHitRate: number;
    requestsPerSecond: number;
  } {
    const now = Date.now();
    const currentSecond = Math.floor(now / 1000);
    const currentRequests = this.rateLimitWindow.get(currentSecond) || 0;
    
    return {
      cacheSize: this.cache.size,
      cacheHitRate: 0, // Would need to track hits vs misses
      requestsPerSecond: currentRequests
    };
  }

  /**
   * Clear cache (useful for testing)
   */
  clearCache(): void {
    this.cache.clear();
  }
}
