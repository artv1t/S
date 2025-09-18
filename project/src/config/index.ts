import dotenv from 'dotenv';
import { Config } from '../types/index.js';

dotenv.config();

export const config: Config = {
  // Environment
  nodeEnv: process.env.NODE_ENV || 'development',
  logLevel: process.env.LOG_LEVEL || 'info',
  
  // RPC Configuration - WORKING ENDPOINTS ONLY
  rpcEndpoints: [
    process.env.RPC_ENDPOINT_1 || 'https://solana.drpc.org',
    process.env.RPC_ENDPOINT_2 || 'https://solana-rpc.publicnode.com',
    process.env.RPC_ENDPOINT_3 || 'https://mainnet.helius-rpc.com/?api-key=7c8922d6-1031-42c1-b4ee-bf5daa29abd4',
    process.env.RPC_ENDPOINT_4 || 'https://api.mainnet-beta.solana.com',
    process.env.RPC_ENDPOINT_5 || 'https://solana.drpc.org',
  ].filter(Boolean) as string[],
  rpcTimeout: parseInt(process.env.RPC_TIMEOUT || '3000'),
  rpcRateLimit: parseInt(process.env.RPC_RATE_LIMIT || '500'),
  rpcBatchSize: parseInt(process.env.RPC_BATCH_SIZE || '50'),
  rpcKeepAlive: process.env.RPC_KEEP_ALIVE === 'true',
  
  // Performance Settings
  maxConcurrentTrades: parseInt(process.env.MAX_CONCURRENT_TRADES || '25'),
  maxConcurrentFilters: parseInt(process.env.MAX_CONCURRENT_FILTERS || '50'),
  maxPositions: parseInt(process.env.MAX_POSITIONS || '100'),
  workerThreads: parseInt(process.env.WORKER_THREADS || '4'),
  memoryLimit: parseInt(process.env.MEMORY_LIMIT || '2048'),
  cpuLimit: parseInt(process.env.CPU_LIMIT || '80'),
  
  // Rate Limiting
  jupiterRateLimit: parseInt(process.env.JUPITER_RATE_LIMIT || '50'),
  dexScreenerRateLimit: parseInt(process.env.DEXSCREENER_RATE_LIMIT || '100'),
  apiRateLimit: parseInt(process.env.API_RATE_LIMIT || '1000'),
  
  // Caching
  cacheTtlMetadata: parseInt(process.env.CACHE_TTL_METADATA || '300'),
  cacheTtlPool: parseInt(process.env.CACHE_TTL_POOL || '60'),
  cacheTtlPrice: parseInt(process.env.CACHE_TTL_PRICE || '30'),
  redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',
  
  // Trading Configuration
  quoteAmount: parseFloat(process.env.QUOTE_AMOUNT || '0.0001'),
  slippageLimit: parseFloat(process.env.SLIPPAGE_LIMIT || '15'),
  maxSlippage: parseFloat(process.env.MAX_SLIPPAGE || '50'),
  takeProfit: parseFloat(process.env.TAKE_PROFIT || '50'),
  stopLoss: parseFloat(process.env.STOP_LOSS || '30'),
  ttlMinutes: parseInt(process.env.TTL_MINUTES || '30'),
  
  // Filters - МЯГКИЕ НАСТРОЙКИ ДЛЯ ТЕСТИРОВАНИЯ
  enableRouteGate: process.env.ENABLE_ROUTE_GATE === 'true',
  enableOnChain: process.env.ENABLE_ON_CHAIN === 'true',
  enableDexScreener: process.env.ENABLE_DEXSCREENER === 'true',
  riskThreshold: parseInt(process.env.RISK_THRESHOLD || '30'), // Снижено с 70 до 30
  filterTimeout: parseInt(process.env.FILTER_TIMEOUT || '10000'), // Увеличено до 10 сек
  
  // Paper Mode
  paperMode: process.env.PAPER_MODE === 'true',
  testMode: process.env.TEST_MODE === 'true',
  dryRun: process.env.DRY_RUN === 'true',
  
  // Monitoring
  enableMetrics: process.env.ENABLE_METRICS === 'true',
  metricsPort: parseInt(process.env.METRICS_PORT || '9090'),
  healthCheckInterval: parseInt(process.env.HEALTH_CHECK_INTERVAL || '5000'),
  performanceLogInterval: parseInt(process.env.PERFORMANCE_LOG_INTERVAL || '10000'),
  
  // Wallet Configuration
  walletPrivateKeyPath: process.env.WALLET_PRIVATE_KEY_PATH || './wallets/wallet.json',
  walletPassphrase: process.env.WALLET_PASSPHRASE || '',
  
  // API Configuration
  apiPort: parseInt(process.env.API_PORT || '3001'),
  apiHost: process.env.API_HOST || 'localhost',
  enableApi: process.env.ENABLE_API === 'true',
  corsOrigin: process.env.CORS_ORIGIN || '*',
  
  // Database
  dbPath: process.env.DB_PATH || './data/bot.db',
  dbBackupInterval: parseInt(process.env.DB_BACKUP_INTERVAL || '3600000'),
  
  // Notifications
  telegramBotToken: process.env.TELEGRAM_BOT_TOKEN || '',
  telegramChatId: process.env.TELEGRAM_CHAT_ID || '',
  discordWebhookUrl: process.env.DISCORD_WEBHOOK_URL || '',
  enableNotifications: process.env.ENABLE_NOTIFICATIONS === 'true',
  
  // Security
  circuitBreakerMaxFailures: parseInt(process.env.CIRCUIT_BREAKER_MAX_FAILURES || '10'),
  dailyLossLimit: parseFloat(process.env.DAILY_LOSS_LIMIT || '0.05'),
  maxExposure: parseFloat(process.env.MAX_EXPOSURE || '0.2'),
  reserveSol: parseFloat(process.env.RESERVE_SOL || '0.01'),
  
  // Filter specific settings - МЯГКИЕ НАСТРОЙКИ
  maxPriceImpact: parseFloat(process.env.MAX_PRICE_IMPACT || '50'), // Увеличено с 15 до 50
  minPoolSize: parseFloat(process.env.MIN_POOL_SIZE || '0.1'), // Снижено с 1 до 0.1
  maxPoolSize: parseFloat(process.env.MAX_POOL_SIZE || '1000'), // Увеличено с 100 до 1000
  maxTop1HolderPercent: parseFloat(process.env.MAX_TOP1_HOLDER_PERCENT || '80'), // Увеличено с 20 до 80
  maxTop5HolderPercent: parseFloat(process.env.MAX_TOP5_HOLDER_PERCENT || '95'), // Увеличено с 50 до 95
  
  // Program IDs
  programIds: {
    pumpFun: process.env.PUMP_FUN_PROGRAM_ID || '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P',
    raydiumClmm: process.env.RAYDIUM_CLMM_PROGRAM_ID || 'CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK',
    raydiumAmm: process.env.RAYDIUM_AMM_PROGRAM_ID || '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8',
    meteora: process.env.METEORA_PROGRAM_ID || 'Eo7WjKq67rjJQS5xOyfPxS5C67L3Kp3C5HZ8N8o8N8o8',
    jupiter: process.env.JUPITER_PROGRAM_ID || 'JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB'
  }
};

// Validate critical configuration
if (config.rpcEndpoints.length < 3) {
  throw new Error('At least 3 RPC endpoints required for high availability');
}

if (config.quoteAmount <= 0) {
  throw new Error('Quote amount must be greater than 0');
}

if (config.maxConcurrentTrades > 50) {
  console.warn('Warning: Very high concurrent trades limit may cause issues');
}