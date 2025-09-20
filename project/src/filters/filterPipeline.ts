import { FilterResult, TokenEvent } from '../types/index.js';
import { RouteGateFilter } from './routeGateFilter.js';
import { OnChainFilter } from './onChainFilter.js';
import { DexScreenerFilter } from './dexscreenerFilter.js';
import { ConsecutiveTracker } from './consecutiveTracker.js';
import { LPProtectionFilter } from './lpProtectionFilter.js';
import { RPCManager } from '../rpc/rpcManager.js';
import { config } from '../config/index.js';
import { EventBus } from '../core/eventBus.js';
import { logSkipFilter } from '../utils/logger.js';
import { tradingLogger } from '../logging/tradingLogger.js';
import { realTimeMonitor } from '../monitoring/realTimeMonitor.js';
import logger from '../utils/logger.js';

/**
 * OPTIMIZED Filter Pipeline - DexScreener ONLY runs if other filters pass!
 * This prevents unnecessary API calls and maximizes throughput
 */
export class FilterPipeline {
  private routeGateFilter: RouteGateFilter;
  private onChainFilter: OnChainFilter;
  private dexScreenerFilter: DexScreenerFilter;
  private consecutiveTracker: ConsecutiveTracker;
  private lpProtectionFilter: LPProtectionFilter;
  private rpcManager: RPCManager;
  private eventBus: EventBus;
  private processingCount = 0;
  private readonly MAX_CONCURRENT = 50;

  constructor() {
    this.routeGateFilter = new RouteGateFilter();
    this.rpcManager = new RPCManager();
    this.onChainFilter = new OnChainFilter(this.rpcManager);
    this.dexScreenerFilter = new DexScreenerFilter();
    this.consecutiveTracker = new ConsecutiveTracker();
    this.lpProtectionFilter = new LPProtectionFilter(this.rpcManager);
    this.eventBus = EventBus.getInstance();
  }

  /**
   * Process token through optimized filter pipeline
   * CRITICAL: DexScreener only runs if other filters pass!
   */
  async processToken(tokenEvent: TokenEvent): Promise<{
    passed: boolean;
    results: FilterResult[];
    totalScore: number;
    reason?: string;
    consecutiveStats?: any;
  }> {
    // Concurrency control
    if (this.processingCount >= this.MAX_CONCURRENT) {
      return {
        passed: false,
        results: [{
          ok: false,
          score: 0,
          reason: 'Pipeline overloaded',
          filterName: 'Pipeline',
          latency: 0
        }],
        totalScore: 0
      };
    }

    this.processingCount++;
    const startTime = Date.now();

    try {
      const results: FilterResult[] = [];
      let totalScore = 0;
      const mintAddress = tokenEvent.mintAddress;

      // PHASE 1: Route Gate Filter (CRITICAL - must pass first)
      if (config.enableRouteGate) {
        const routeGateResult = await this.runFilter('RouteGate', () => 
          this.routeGateFilter.execute(mintAddress)
        );
        
        results.push(routeGateResult);
        this.eventBus.emitFilterResult(mintAddress, routeGateResult);
        
        this.consecutiveTracker.trackFilterResult(
          mintAddress,
          routeGateResult.ok,
          routeGateResult.filterName,
          routeGateResult.score
        );
        
        tradingLogger.logFilterResult({
          timestamp: new Date().toISOString(),
          mintAddress,
          filterName: 'routeGate',
          passed: routeGateResult.ok,
          score: routeGateResult.score,
          latency: routeGateResult.latency,
          reason: routeGateResult.reason || 'No reason provided',
          cacheHit: false
        });
        realTimeMonitor.tokenFiltered(mintAddress, routeGateResult.ok);
        
        // EARLY EXIT: If Route Gate fails, don't waste time on other filters
        if (!routeGateResult.ok) {
          logSkipFilter('RouteGate', mintAddress, routeGateResult.reason || 'Failed', routeGateResult.score);
          return {
            passed: false,
            results,
            totalScore: 0,
            reason: `RouteGate failed: ${routeGateResult.reason}`
          };
        }
        totalScore += routeGateResult.score;
      }

      // PHASE 2: On-Chain Filter (Fast, parallel with Route Gate success)
      if (config.enableOnChain) {
        const onChainResult = await this.runFilter('OnChain', () =>
          this.onChainFilter.execute(mintAddress)
        );
        
        results.push(onChainResult);
        this.eventBus.emitFilterResult(mintAddress, onChainResult);
        
        this.consecutiveTracker.trackFilterResult(
          mintAddress,
          onChainResult.ok,
          onChainResult.filterName,
          onChainResult.score
        );
        
        tradingLogger.logFilterResult({
          timestamp: new Date().toISOString(),
          mintAddress,
          filterName: 'onChain',
          passed: onChainResult.ok,
          score: onChainResult.score,
          latency: onChainResult.latency,
          reason: onChainResult.reason || 'No reason provided',
          cacheHit: false
        });
        realTimeMonitor.tokenFiltered(mintAddress, onChainResult.ok);
        
        // EARLY EXIT: If On-Chain fails, don't call DexScreener
        if (!onChainResult.ok) {
          logSkipFilter('OnChain', mintAddress, onChainResult.reason || 'Failed', onChainResult.score);
          return {
            passed: false,
            results,
            totalScore: totalScore + onChainResult.score,
            reason: `OnChain failed: ${onChainResult.reason}`
          };
        }
        totalScore += onChainResult.score;
      }

      // PHASE 3: DexScreener Filter (ONLY if previous filters passed!)
      // This is the key optimization - don't waste API calls on bad tokens
      if (config.enableDexScreener) {
        const dexScreenerResult = await this.runFilter('DexScreener', () =>
          this.dexScreenerFilter.execute(mintAddress)
        );
        
        results.push(dexScreenerResult);
        this.eventBus.emitFilterResult(mintAddress, dexScreenerResult);
        
        this.consecutiveTracker.trackFilterResult(
          mintAddress,
          dexScreenerResult.ok,
          dexScreenerResult.filterName,
          dexScreenerResult.score
        );
        
        tradingLogger.logFilterResult({
          timestamp: new Date().toISOString(),
          mintAddress,
          filterName: 'dexScreener',
          passed: dexScreenerResult.ok,
          score: dexScreenerResult.score,
          latency: dexScreenerResult.latency,
          reason: dexScreenerResult.reason || 'No reason provided',
          cacheHit: false
        });
        realTimeMonitor.tokenFiltered(mintAddress, dexScreenerResult.ok);
        
        if (!dexScreenerResult.ok) {
          logSkipFilter('DexScreener', mintAddress, dexScreenerResult.reason || 'Failed', dexScreenerResult.score);
          return {
            passed: false,
            results,
            totalScore: totalScore + dexScreenerResult.score,
            reason: `DexScreener failed: ${dexScreenerResult.reason}`
          };
        }
        totalScore += dexScreenerResult.score;
      }

      const consecutiveStats = this.consecutiveTracker.getTokenStats(mintAddress);
      const consecutivePassed = this.consecutiveTracker.isConsecutivelyPassed(mintAddress);

      // Calculate final score and decision
      const averageScore = results.length > 0 ? totalScore / results.length : 0;
      let passed = averageScore >= config.riskThreshold && results.every(r => r.ok);
      let reason = '';

      if (!passed) {
        reason = 'Initial filters failed or score below threshold';
      } else if (!consecutivePassed) {
        reason = `Consecutive requirement not met (${consecutiveStats.passedAttempts}/${config.consecutiveFilterMatches} over ${Math.round(consecutiveStats.timeSpread / 1000)}s)`;
        passed = false;
      } else {
        try {
          const lpResult = await this.lpProtectionFilter.execute(mintAddress, tokenEvent.poolAddress);
          results.push(lpResult);
          
          if (!lpResult.ok) {
            passed = false;
            reason = `LP Protection failed: ${lpResult.reason}`;
          } else {
            reason = 'All filters passed including consecutive and LP protection';
          }

          logger.info(`🔒 LP Protection: ${lpResult.ok ? '✅' : '❌'} (${lpResult.score}/100) - ${lpResult.reason || 'No reason'}`);
        } catch (lpError) {
          logger.warn(`LP Protection check failed: ${lpError}`);
          passed = false;
          reason = 'LP Protection check error';
        }
      }

      if (passed) {
        logger.info({
          code: 'FILTER_PASSED',
          mintAddress,
          totalScore: averageScore,
          results: results.length,
          latency: Date.now() - startTime
        });
      }

      logger.info(`🎯 Final Result: ${passed ? '✅ APPROVED' : '❌ REJECTED'} - ${reason}`);
      logger.info(`📈 Consecutive Stats: ${consecutiveStats.passedAttempts}/${config.consecutiveFilterMatches} attempts over ${Math.round(consecutiveStats.timeSpread / 1000)}s`);

      return {
        passed,
        results,
        totalScore: averageScore,
        reason,
        consecutiveStats
      };

    } catch (error) {
      logger.error('Filter pipeline error:', error);
      return {
        passed: false,
        results: [{
          ok: false,
          score: 0,
          reason: 'Pipeline error',
          filterName: 'Pipeline',
          latency: Date.now() - startTime
        }],
        totalScore: 0,
        reason: 'Pipeline error'
      };
    } finally {
      this.processingCount--;
    }
  }

  /**
   * Run individual filter with timeout and error handling
   */
  private async runFilter(
    filterName: string,
    filterFunction: () => Promise<FilterResult>
  ): Promise<FilterResult> {
    const startTime = Date.now();
    
    try {
      const result = await Promise.race([
        filterFunction(),
        this.createTimeoutPromise(config.filterTimeout, filterName)
      ]);

      const latency = Date.now() - startTime;
      return {
        ...result,
        filterName,
        latency
      };
    } catch (error) {
      const latency = Date.now() - startTime;
      return {
        ok: false,
        score: 0,
        reason: error instanceof Error ? error.message : 'Unknown error',
        filterName,
        latency
      };
    }
  }

  /**
   * Create timeout promise for filter execution
   */
  private createTimeoutPromise(timeout: number, filterName: string): Promise<FilterResult> {
    return new Promise((_, reject) => {
      setTimeout(() => {
        reject(new Error(`${filterName} filter timeout after ${timeout}ms`));
      }, timeout);
    });
  }

  /**
   * Get pipeline performance metrics
   */
  getMetrics(): {
    processingCount: number;
    maxConcurrent: number;
    utilizationPercent: number;
    consecutive: any;
    lpProtection: any;
  } {
    return {
      processingCount: this.processingCount,
      maxConcurrent: this.MAX_CONCURRENT,
      utilizationPercent: Math.round((this.processingCount / this.MAX_CONCURRENT) * 100),
      consecutive: this.consecutiveTracker.getOverallStats(),
      lpProtection: this.lpProtectionFilter.getMetrics()
    };
  }

  /**
   * Clear all filter caches
   */
  clearCaches(): void {
    this.consecutiveTracker.clear();
    this.lpProtectionFilter.clearCache();
  }

  /**
   * Destroy all filters and cleanup resources
   */
  destroy(): void {
    this.consecutiveTracker.destroy();
    this.clearCaches();
  }
}
