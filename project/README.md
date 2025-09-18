# 🚀 Solana Sniper Bot - High Performance Trading Bot

A high-performance, modular Solana sniper bot built with TypeScript that can process **1000+ events per second** and automatically trade new tokens with advanced filtering and risk management.

## ⚡ Key Features

### 🎯 High Performance
- **1000+ events/sec** processing capability
- **<50ms** average processing latency
- **Parallel processing** of 50+ tokens simultaneously
- **10+ RPC endpoints** with automatic failover
- **Aggressive caching** for optimal performance

### 🔍 Smart Token Detection
- **Real-time detection** via `onProgramAccountChange`
- **Multi-DEX support**: PumpFun, Raydium, Meteora, Jupiter
- **Event deduplication** and queue management
- **Backup polling** for missed events

### 🛡️ Advanced Filtering (Optimized Pipeline)
1. **Route Gate Filter** (Jupiter API) - Runs FIRST
2. **On-Chain Filter** (Parallel with Route Gate)
3. **DexScreener Filter** - **ONLY runs if others pass!** ⚡

This optimization prevents unnecessary API calls and maximizes throughput.

### 💰 Automated Trading
- **Paper mode** for safe testing
- **Live mode** for real trading
- **Take Profit** (50% default, configurable)
- **Stop Loss** (30% default, configurable)
- **TTL** (30 minutes default, configurable)
- **Position management** up to 100 concurrent positions

### 🔒 Risk Management
- **Circuit breaker** (auto-pause on failures)
- **Daily loss limits**
- **Exposure limits**
- **Rate limiting** on all APIs
- **Comprehensive error handling**

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd solana-sniper-bot

# Install dependencies
npm install

# Copy environment template
cp .env.example .env
```

### 2. Configuration

Edit `.env` file with your settings:

```bash
# CRITICAL: Set your RPC endpoints (need 3+ for high availability)
RPC_ENDPOINT_1=https://api.mainnet-beta.solana.com
RPC_ENDPOINT_2=https://solana-api.projectserum.com
RPC_ENDPOINT_3=https://rpc.ankr.com/solana
# Add more RPC endpoints for better performance

# Trading settings
PAPER_MODE=true              # Start with paper mode!
QUOTE_AMOUNT=0.0001          # SOL amount per trade
TAKE_PROFIT=50               # Take profit percentage
STOP_LOSS=30                 # Stop loss percentage
TTL_MINUTES=30               # Position time-to-live

# Performance settings
MAX_CONCURRENT_TRADES=25     # Parallel trades
MAX_CONCURRENT_FILTERS=50    # Parallel filters
RPC_RATE_LIMIT=500          # Requests per second per RPC
```

### 3. Paper Mode Testing (RECOMMENDED FIRST)

```bash
# Build the project
npm run build

# Start in paper mode (safe testing)
npm run start:paper

# Or use development mode
npm run dev:paper
```

### 4. Live Mode (Real Trading)

⚠️ **WARNING: Only use live mode after thorough testing in paper mode!**

```bash
# Set up wallet (NEVER commit private keys!)
mkdir wallets
# Add your wallet JSON file to ./wallets/

# Update .env
PAPER_MODE=false
WALLET_PRIVATE_KEY_PATH=./wallets/your-wallet.json

# Start live trading
npm run start:live
```

## 📊 Performance Monitoring

### API Endpoints

```bash
# Health check
curl http://localhost:3001/health

# Performance metrics
curl http://localhost:3001/metrics

# Current positions
curl http://localhost:3001/positions

# Bot status
curl http://localhost:3001/status
```

### Performance Targets

The bot is designed to achieve:

- ✅ **Events/sec**: 1000+
- ✅ **Processing latency**: <50ms
- ✅ **Memory usage**: <2GB
- ✅ **CPU usage**: <80%
- ✅ **Success rate**: >95%
- ✅ **Error rate**: <1%
- ✅ **Uptime**: >99.9%

## 🔧 Configuration Guide

### Filter Configuration

```bash
# Enable/disable filters
ENABLE_ROUTE_GATE=true       # Jupiter liquidity check
ENABLE_ON_CHAIN=true         # On-chain validation
ENABLE_DEXSCREENER=true      # Social/metadata check

# Risk threshold (0-100)
RISK_THRESHOLD=70            # Minimum score to pass
```

### Performance Tuning

```bash
# Concurrency limits
MAX_CONCURRENT_TRADES=25     # Max parallel trades
MAX_CONCURRENT_FILTERS=50    # Max parallel filters
MAX_POSITIONS=100            # Max open positions

# RPC settings
RPC_TIMEOUT=3000             # RPC timeout (ms)
RPC_RATE_LIMIT=500           # Requests per second
RPC_BATCH_SIZE=50            # Batch size for RPC calls

# Caching
CACHE_TTL_METADATA=300       # Metadata cache (seconds)
CACHE_TTL_POOL=60            # Pool cache (seconds)
CACHE_TTL_PRICE=30           # Price cache (seconds)
```

## 🛡️ Security & Safety

### Pre-Trading Checklist

- [ ] ✅ Tested thoroughly in paper mode
- [ ] ✅ Small test amounts only (start with 0.001 SOL)
- [ ] ✅ Circuit breaker configured
- [ ] ✅ Daily loss limits set
- [ ] ✅ Monitoring alerts enabled
- [ ] ✅ Emergency stop procedure ready
- [ ] ✅ Wallet security verified
- [ ] ✅ RPC endpoints tested

### Safety Rules

1. **🔒 NEVER commit private keys** to version control
2. **📝 Always start with paper mode** for testing
3. **💰 Use small amounts** for initial live testing
4. **⚡ Set circuit breaker limits** to prevent large losses
5. **📊 Monitor performance** and set up alerts
6. **🛑 Have an emergency stop** procedure ready

### Risk Management

```bash
# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD=10  # Max consecutive failures
MAX_DAILY_LOSS=0.05          # Max daily loss (SOL)
MAX_EXPOSURE=0.2             # Max total exposure (SOL)
RESERVE_SOL=0.01             # Reserve for fees
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

### Load Testing

```bash
# Simulate high event load
npm run load-test

# This will test:
# - 5000 events/minute processing
# - Concurrent filter execution
# - Memory usage under load
# - Error handling
```

### Integration Tests

```bash
# Full paper mode cycle test
npm run test:integration

# This tests:
# - Token detection → filtering → trading
# - Position management
# - Circuit breaker
# - Performance metrics
```

## 📁 Project Structure

```
src/
├── core/                    # Core bot logic
│   ├── botManager.ts       # Main bot orchestrator
│   └── eventBus.ts         # High-performance event system
├── rpc/                    # RPC connection management
│   └── rpcManager.ts       # 10+ RPC pool with failover
├── detector/               # Token detection
│   └── tokenDetector.ts    # Real-time event processing
├── filters/                # Token filtering pipeline
│   ├── filterPipeline.ts   # Optimized filter orchestration
│   ├── routeGateFilter.ts  # Jupiter liquidity check
│   ├── onChainFilter.ts    # On-chain validation
│   └── dexscreenerFilter.ts # Social/metadata (optimized)
├── trader/                 # Trading execution
│   └── trader.ts           # Parallel trade execution
├── position/               # Position management
│   └── positionManager.ts  # TP/SL/TTL management
├── wallet/                 # Wallet management
│   └── walletManager.ts    # Multi-wallet support
├── paper/                  # Paper trading simulation
│   └── paperEngine.ts      # Safe testing environment
├── api/                    # REST API server
│   └── server.ts           # Metrics and control API
├── utils/                  # Utilities
│   ├── logger.ts           # Structured logging
│   └── config.ts           # Configuration management
└── types/                  # TypeScript definitions
    └── index.ts            # All type definitions
```

## 🔍 Filter Pipeline Optimization

The key performance optimization is the **sequential filter pipeline**:

1. **Route Gate Filter** (Jupiter API) - Runs FIRST
   - If this fails → immediate exit (no other API calls)
   - Prevents wasting DexScreener API calls on illiquid tokens

2. **On-Chain Filter** - Runs in parallel with Route Gate success
   - Fast on-chain validation
   - No external API calls

3. **DexScreener Filter** - **ONLY runs if others pass**
   - This is the key optimization!
   - Saves 90%+ of unnecessary API calls
   - Maximizes throughput

## 📈 Performance Optimization Tips

### RPC Optimization
- Use **10+ RPC endpoints** for high availability
- Enable **connection keep-alive**
- Use **batch requests** (50 per batch)
- Implement **health checks** every 5 seconds

### Caching Strategy
- **Metadata cache**: 5 minutes
- **Pool cache**: 1 minute  
- **Price cache**: 30 seconds
- **Filter results**: 1-5 minutes depending on filter

### Memory Management
- **Event deduplication** with size limits
- **Periodic cache cleanup**
- **Queue size limits** (10,000 events max)
- **Batch processing** (100 events per batch)

## 🚨 Common Issues & Solutions

### Issue: Low Events/Second
**Solution**: 
- Add more RPC endpoints
- Increase `MAX_CONCURRENT_FILTERS`
- Check RPC health status
- Verify network connectivity

### Issue: High Memory Usage
**Solution**:
- Reduce cache TTL values
- Lower `MAX_POSITIONS`
- Check for memory leaks in logs
- Restart bot periodically

### Issue: API Rate Limits
**Solution**:
- Reduce `JUPITER_RATE_LIMIT`
- Reduce `DEXSCREENER_RATE_LIMIT`
- Add delays between requests
- Use multiple API keys if available

### Issue: Circuit Breaker Triggered
**Solution**:
- Check RPC endpoint health
- Verify wallet balance
- Review recent error logs
- Adjust risk parameters

## 📞 Support & Monitoring

### Logging
All events are logged with structured JSON:

```json
{
  "code": "BUY_SUCCESS",
  "mintAddress": "...",
  "amount": 1000000,
  "price": 0.0001,
  "txSignature": "...",
  "timestamp": 1640995200000
}
```

### Log Codes
- `DETECTED_POOL`: New pool found
- `SKIP_ROUTE_GATE`: Failed Route Gate filter
- `SKIP_ON_CHAIN`: Failed On-Chain filter
- `SKIP_DEXSCREENER`: Failed DexScreener filter
- `BUY_SUCCESS`: Successful purchase
- `BUY_ERROR`: Purchase failed
- `SELL_TP`: Take profit triggered
- `SELL_SL`: Stop loss triggered
- `SELL_TTL`: TTL timeout
- `CIRCUIT_BREAKER`: Circuit breaker activated

### Notifications (Optional)
Set up Telegram/Discord webhooks:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DISCORD_WEBHOOK=your_webhook_url
```

## 🔄 Updates & Maintenance

### Regular Maintenance
- **Monitor RPC health** daily
- **Check error rates** and adjust limits
- **Review performance metrics** weekly
- **Update dependencies** monthly
- **Backup wallet files** regularly

### Performance Monitoring
- Watch memory usage trends
- Monitor API rate limit usage
- Check filter success rates
- Review trade success rates

## ⚠️ Important Disclaimers

- **🚨 HIGH RISK**: Cryptocurrency trading involves substantial risk
- **💰 LOSS POTENTIAL**: You can lose all invested funds
- **🔬 EXPERIMENTAL**: This is beta software with potential bugs
- **📚 EDUCATIONAL**: Intended for educational purposes
- **🔒 YOUR RESPONSIBILITY**: Always verify settings before trading
- **⚖️ NO WARRANTIES**: Software provided as-is without guarantees

## 📄 License

MIT License - see LICENSE file for details.

---

**Remember: Always start with paper mode, use small amounts for testing, and understand the risks before live trading!**

🚀 **Happy Trading!** 🚀