import { FilterResult } from '../types/index.js';
import { RouteGateFilter } from './routeGateFilter.js';
import { OnChainFilter } from './onChainFilter.js';
import { DexScreenerFilter } from './dexscreenerFilter.js';
import { RPCManager } from '../rpc/rpcManager.js';
import { config } from '../config/index.js';
import { EventBus } from '../core/eventBus.js';
import { logSkipFilter } from '../utils/logger.js';
import logger from '../utils/logger.js';

/**
 * OPTIMIZED Filter Pipeline - DexScreener ONLY runs if other filters pass!
 * This prevents unnecessary API calls and maximizes throughput
 */
export class FilterPipeline {
  private routeGateFilter: RouteGateFilter;
  private onChainFilter: OnChainFilter;
  private dexScreenerFilter: DexScreenerFilter;
  private rpcManager: RPCManager;
  private eventBus: EventBus;
  private processingCount = 0;
  private readonly MAX_CONCURRENT = 50;

  constructor() {
    this.routeGateFilter = new RouteGateFilter();
    this.rpcManager = new RPCManager();
    this.onChainFilter = new OnChainFilter(this.rpcManager);
    this.dexScreenerFilter = new DexScreenerFilter();
    this.eventBus = EventBus.getInstance();
  }

  /**
   * Process token through optimized filter pipeline
   * CRITICAL: DexScreener only runs if other filters pass!
   */
  async processToken(mintAddress: string): Promise<{
    passed: boolean;
    results: FilterResult[];
    totalScore: number;
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

      // PHASE 1: Route Gate Filter (CRITICAL - must pass first)
      if (config.enableRouteGate) {
        const routeGateResult = await this.runFilter('RouteGate', () => 
          this.routeGateFilter.execute(mintAddress)
        );
        
        results.push(routeGateResult);
        this.eventBus.emitFilterResult(mintAddress, routeGateResult);
        
        // EARLY EXIT: If Route Gate fails, don't waste time on other filters
        if (!routeGateResult.ok) {
          logSkipFilter('RouteGate', mintAddress, routeGateResult.reason || 'Failed', routeGateResult.score);
          return {
            passed: false,
            results,
            totalScore: 0
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
        
        // EARLY EXIT: If On-Chain fails, don't call DexScreener
        if (!onChainResult.ok) {
          logSkipFilter('OnChain', mintAddress, onChainResult.reason || 'Failed', onChainResult.score);
          return {
            passed: false,
            results,
            totalScore: totalScore + onChainResult.score
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
        
        if (!dexScreenerResult.ok) {
          logSkipFilter('DexScreener', mintAddress, dexScreenerResult.reason || 'Failed', dexScreenerResult.score);
          return {
            passed: false,
            results,
            totalScore: totalScore + dexScreenerResult.score
          };
        }
        totalScore += dexScreenerResult.score;
      }

      // Calculate final score and decision
      const averageScore = results.length > 0 ? totalScore / results.length : 0;
      const passed = averageScore >= config.riskThreshold && results.every(r => r.ok);

      if (passed) {
        logger.info({
          code: 'FILTER_PASSED',
          mintAddress,
          totalScore: averageScore,
          results: results.length,
          latency: Date.now() - startTime
        });
      }

      return {
        passed,
        results,
        totalScore: averageScore
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
        totalScore: 0
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
  } {
    return {
      processingCount: this.processingCount,
      maxConcurrent: this.MAX_CONCURRENT,
      utilizationPercent: Math.round((this.processingCount / this.MAX_CONCURRENT) * 100)
    };
  }
}