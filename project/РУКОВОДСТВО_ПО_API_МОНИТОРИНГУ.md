# 📊 РУКОВОДСТВО ПО API МОНИТОРИНГУ БОТА

## 🎯 ОБЗОР API СИСТЕМЫ

Бот предоставляет полный набор REST API endpoints для мониторинга всех аспектов работы в реальном времени. API позволяет отслеживать торговлю, производительность, балансы и управлять ботом удаленно.

### 🔥 КЛЮЧЕВЫЕ ВОЗМОЖНОСТИ:
- ✅ **Real-time мониторинг** торговых операций
- ✅ **Статистика производительности** и метрики системы
- ✅ **Управление позициями** и кошельками
- ✅ **Контроль фильтров** и их эффективности
- ✅ **WebSocket подключения** для live обновлений
- ✅ **Система безопасности** и emergency controls

---

## 🚀 БАЗОВЫЕ ENDPOINTS

### 🏥 Проверка здоровья системы
```bash
# Общее состояние бота
curl http://localhost:3001/health | jq

# Ответ:
{
  "status": "healthy",
  "timestamp": "2025-09-19T16:30:00.000Z",
  "uptime": 3600000,
  "bot": {
    "running": true,
    "mode": "live",
    "totalEvents": 15927,
    "activeTrades": 2
  },
  "rpc": {
    "healthy": 2,
    "total": 2,
    "avgLatency": 76
  },
  "memory": {
    "used": 345,
    "free": 7655,
    "usage": "4.3%"
  }
}
```

### 📊 Статус бота
```bash
# Детальный статус работы
curl http://localhost:3001/api/bot/status | jq

# Ответ:
{
  "isRunning": true,
  "mode": "live",
  "startTime": "2025-09-19T16:29:09.661Z",
  "uptime": 3600000,
  "currentBalance": 0.0495,
  "activeTrades": 2,
  "totalTrades": 15,
  "successRate": 86.7,
  "totalPnL": 0.0025,
  "dailyPnL": 0.0025
}
```

---

## 💰 МОНИТОРИНГ ТОРГОВЛИ

### 📈 Активные позиции
```bash
# Все открытые позиции
curl http://localhost:3001/api/positions | jq

# Ответ:
{
  "positions": [
    {
      "id": "pos_001",
      "mintAddress": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
      "symbol": "BONK",
      "buyPrice": 0.00001,
      "currentPrice": 0.000012,
      "amount": 1000000,
      "solInvested": 0.0001,
      "currentValue": 0.00012,
      "pnl": 0.00002,
      "pnlPercent": 20.0,
      "buyTime": "2025-09-19T16:30:15.123Z",
      "takeProfit": 0.000015,
      "stopLoss": 0.000008,
      "ttl": "2025-09-19T17:00:15.123Z"
    }
  ],
  "totalPositions": 1,
  "totalInvested": 0.0001,
  "totalValue": 0.00012,
  "totalPnL": 0.00002
}
```

### 📊 История торговли
```bash
# Последние сделки
curl http://localhost:3001/api/trading/history?limit=10 | jq

# Сделки за период
curl "http://localhost:3001/api/trading/history?from=2025-09-19T00:00:00Z&to=2025-09-19T23:59:59Z" | jq

# Ответ:
{
  "trades": [
    {
      "id": "trade_001",
      "timestamp": "2025-09-19T16:30:15.123Z",
      "mintAddress": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
      "symbol": "BONK",
      "action": "BUY",
      "amount": 1000000,
      "price": 0.00001,
      "solAmount": 0.0001,
      "txHash": "5J7...abc",
      "status": "completed"
    }
  ],
  "totalTrades": 15,
  "successfulTrades": 13,
  "failedTrades": 2,
  "totalVolume": 0.0015,
  "totalPnL": 0.0025
}
```

### 💼 Управление позициями
```bash
# Закрыть позицию
curl -X POST http://localhost:3001/api/positions/close \
  -H "Content-Type: application/json" \
  -d '{"positionId": "pos_001"}'

# Обновить Take Profit / Stop Loss
curl -X PUT http://localhost:3001/api/positions/update \
  -H "Content-Type: application/json" \
  -d '{
    "positionId": "pos_001",
    "takeProfit": 25.0,
    "stopLoss": 15.0
  }'

# Закрыть все позиции (Emergency)
curl -X POST http://localhost:3001/api/positions/close-all
```

---

## 💳 МОНИТОРИНГ КОШЕЛЬКОВ

### 💰 Балансы кошельков
```bash
# Все балансы
curl http://localhost:3001/api/wallets/balances | jq

# Ответ:
{
  "wallets": [
    {
      "name": "main_wallet",
      "address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
      "solBalance": 0.0495,
      "tokens": [
        {
          "mintAddress": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
          "symbol": "BONK",
          "balance": 1000000,
          "value": 0.00012
        }
      ],
      "totalValue": 0.04962
    }
  ],
  "totalSOL": 0.0495,
  "totalTokenValue": 0.00012,
  "totalPortfolioValue": 0.04962
}
```

### 📊 История балансов
```bash
# График изменения баланса
curl "http://localhost:3001/api/wallets/balance-history?period=24h" | jq

# Ответ:
{
  "history": [
    {
      "timestamp": "2025-09-19T16:00:00Z",
      "solBalance": 0.05,
      "tokenValue": 0,
      "totalValue": 0.05
    },
    {
      "timestamp": "2025-09-19T17:00:00Z", 
      "solBalance": 0.0495,
      "tokenValue": 0.00012,
      "totalValue": 0.04962
    }
  ],
  "startValue": 0.05,
  "endValue": 0.04962,
  "change": -0.00038,
  "changePercent": -0.76
}
```

---

## 🔍 МОНИТОРИНГ ФИЛЬТРОВ

### 📊 Статистика фильтров
```bash
# Общая статистика всех фильтров
curl http://localhost:3001/api/bot/filters/stats | jq

# Ответ:
{
  "routeGate": {
    "processed": 15927,
    "passed": 871,
    "passRate": 5.47,
    "avgLatency": 250,
    "timeouts": 12450,
    "errors": 23
  },
  "onChain": {
    "processed": 871,
    "passed": 45,
    "passRate": 5.17,
    "avgLatency": 180,
    "rpcErrors": 5,
    "invalidTokens": 821
  },
  "dexScreener": {
    "processed": 45,
    "passed": 12,
    "passRate": 26.67,
    "avgLatency": 320,
    "socialChecksFailed": 20,
    "metadataIssues": 13
  },
  "overall": {
    "tokensDiscovered": 15927,
    "totalPassed": 12,
    "overallPassRate": 0.075,
    "avgProcessingTime": 750
  }
}
```

### 🔧 Управление фильтрами
```bash
# Включить/отключить фильтр
curl -X POST http://localhost:3001/api/bot/filters/toggle \
  -H "Content-Type: application/json" \
  -d '{"filter": "dexscreener", "enabled": false}'

# Обновить настройки фильтра
curl -X PUT http://localhost:3001/api/bot/filters/routegate \
  -H "Content-Type: application/json" \
  -d '{
    "minScore": 75,
    "maxPriceImpact": 8,
    "enabled": true
  }'

# Сбросить статистику
curl -X POST http://localhost:3001/api/bot/filters/reset-stats
```

---

## 📊 МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ

### ⚡ Системные метрики
```bash
# Детальные метрики производительности
curl http://localhost:3001/api/metrics | jq

# Ответ:
{
  "timestamp": "2025-09-19T17:00:00Z",
  "uptime": 3600000,
  "data": {
    "events": {
      "total": 15927,
      "perSecond": 4.42,
      "peak": 45.5
    },
    "memory": {
      "used": 345,
      "free": 7655,
      "usage": 4.3,
      "peak": 387
    },
    "rpc": {
      "healthy": 2,
      "total": 2,
      "avgLatency": 76,
      "requestsPerSecond": 8.5,
      "errors": 0
    },
    "filters": {
      "avgLatency": 250,
      "throughput": 4.2,
      "errorRate": 0.14
    }
  }
}
```

### 📈 Торговые метрики
```bash
# Статистика торговли
curl http://localhost:3001/api/metrics/trading | jq

# Ответ:
{
  "totalTrades": 15,
  "successfulTrades": 13,
  "failedTrades": 2,
  "successRate": 86.67,
  "totalVolume": 0.0015,
  "totalPnL": 0.0025,
  "avgTradeSize": 0.0001,
  "avgHoldTime": 1800000,
  "bestTrade": {
    "pnl": 0.0008,
    "pnlPercent": 80.0,
    "symbol": "BONK"
  },
  "worstTrade": {
    "pnl": -0.0002,
    "pnlPercent": -20.0,
    "symbol": "PEPE"
  }
}
```

---

## 📋 СЕССИИ И ЛОГИРОВАНИЕ

### 📊 Текущая сессия
```bash
# Данные текущей сессии
curl http://localhost:3001/api/bot/session/current | jq

# Ответ:
{
  "sessionId": "session_1758299349661",
  "sessionNumber": 1,
  "startTime": "2025-09-19T16:29:09.661Z",
  "duration": 3600000,
  "startingBalance": 0.05,
  "currentBalance": 0.04962,
  "activeTrades": 2,
  "completedTrades": 13,
  "totalPnL": -0.00038,
  "filterStats": {
    "tokensDiscovered": 15927,
    "totalPassed": 12
  },
  "performanceMetrics": {
    "peakTokensPerSecond": 45.5,
    "avgMemoryUsage": 345
  }
}
```

### 📚 История сессий
```bash
# Все сессии
curl http://localhost:3001/api/bot/sessions/all | jq

# Конкретная сессия
curl http://localhost:3001/api/bot/session/3 | jq

# Последняя завершенная сессия
curl http://localhost:3001/api/bot/session/latest | jq
```

---

## 🛡️ БЕЗОПАСНОСТЬ И КОНТРОЛЬ

### 🚨 Emergency Controls
```bash
# Немедленная остановка всех операций
curl -X POST http://localhost:3001/api/safety/emergency-stop

# Активировать Circuit Breaker
curl -X POST http://localhost:3001/api/safety/circuit-breaker

# Проверить лимиты безопасности
curl http://localhost:3001/api/safety/limits | jq

# Ответ:
{
  "dailyLossLimit": 0.05,
  "currentDailyLoss": 0.00038,
  "maxExposure": 0.2,
  "currentExposure": 0.0002,
  "circuitBreakerActive": false,
  "emergencyStopActive": false,
  "riskLevel": "low"
}
```

### 🔧 Управление ботом
```bash
# Запуск бота
curl -X POST http://localhost:3001/api/bot/start

# Остановка бота
curl -X POST http://localhost:3001/api/bot/stop

# Перезапуск бота
curl -X POST http://localhost:3001/api/bot/restart

# Изменение режима
curl -X POST http://localhost:3001/api/bot/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "paper"}'
```

---

## 🌐 WEBSOCKET МОНИТОРИНГ

### 📡 Real-time подключение
```javascript
// Подключение к WebSocket для live обновлений
const ws = new WebSocket('ws://localhost:3001/ws');

ws.onopen = function() {
  console.log('Connected to bot WebSocket');
  
  // Подписка на события
  ws.send(JSON.stringify({
    action: 'subscribe',
    events: ['trades', 'positions', 'balance', 'filters']
  }));
};

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'trade_executed':
      console.log('New trade:', data.trade);
      break;
      
    case 'position_updated':
      console.log('Position update:', data.position);
      break;
      
    case 'balance_changed':
      console.log('Balance changed:', data.balance);
      break;
      
    case 'filter_result':
      console.log('Filter result:', data.result);
      break;
  }
};
```

### 📊 Типы WebSocket событий
```javascript
// Торговые события
{
  "type": "trade_executed",
  "timestamp": "2025-09-19T17:00:00Z",
  "trade": {
    "action": "BUY",
    "symbol": "BONK",
    "amount": 1000000,
    "price": 0.00001
  }
}

// Обновления позиций
{
  "type": "position_updated", 
  "timestamp": "2025-09-19T17:00:00Z",
  "position": {
    "id": "pos_001",
    "pnl": 0.00002,
    "pnlPercent": 20.0
  }
}

// Изменения баланса
{
  "type": "balance_changed",
  "timestamp": "2025-09-19T17:00:00Z",
  "balance": {
    "sol": 0.04962,
    "totalValue": 0.04962
  }
}
```

---

## 📱 СОЗДАНИЕ DASHBOARD

### 🖥️ HTML Dashboard пример
```html
<!DOCTYPE html>
<html>
<head>
    <title>Solana Bot Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div id="status"></div>
    <div id="balance"></div>
    <div id="positions"></div>
    <canvas id="pnlChart"></canvas>
    
    <script>
        // Подключение к API
        async function updateDashboard() {
            try {
                // Статус бота
                const status = await fetch('/api/bot/status').then(r => r.json());
                document.getElementById('status').innerHTML = `
                    <h2>Bot Status: ${status.isRunning ? 'Running' : 'Stopped'}</h2>
                    <p>Mode: ${status.mode}</p>
                    <p>Total PnL: ${status.totalPnL} SOL</p>
                `;
                
                // Баланс
                const balance = await fetch('/api/wallets/balances').then(r => r.json());
                document.getElementById('balance').innerHTML = `
                    <h3>Balance: ${balance.totalSOL} SOL</h3>
                `;
                
                // Позиции
                const positions = await fetch('/api/positions').then(r => r.json());
                let positionsHtml = '<h3>Active Positions:</h3>';
                positions.positions.forEach(pos => {
                    positionsHtml += `
                        <div>
                            ${pos.symbol}: ${pos.pnlPercent.toFixed(2)}% 
                            (${pos.pnl.toFixed(6)} SOL)
                        </div>
                    `;
                });
                document.getElementById('positions').innerHTML = positionsHtml;
                
            } catch (error) {
                console.error('Dashboard update error:', error);
            }
        }
        
        // Обновление каждые 5 секунд
        setInterval(updateDashboard, 5000);
        updateDashboard();
    </script>
</body>
</html>
```

---

## 📊 АВТОМАТИЗАЦИЯ МОНИТОРИНГА

### 🔔 Telegram уведомления
```bash
#!/bin/bash
# telegram_alerts.sh

BOT_TOKEN="your_telegram_bot_token"
CHAT_ID="your_chat_id"

# Функция отправки сообщения
send_telegram() {
    curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="$1"
}

# Мониторинг каждые 60 секунд
while true; do
    # Проверка статуса бота
    STATUS=$(curl -s http://localhost:3001/api/bot/status | jq -r '.isRunning')
    
    if [ "$STATUS" != "true" ]; then
        send_telegram "🚨 BOT STOPPED! Check immediately!"
    fi
    
    # Проверка PnL
    PNL=$(curl -s http://localhost:3001/api/bot/status | jq -r '.totalPnL')
    if (( $(echo "$PNL < -0.01" | bc -l) )); then
        send_telegram "📉 Daily loss exceeded -0.01 SOL: $PNL"
    fi
    
    sleep 60
done
```

### 📈 Grafana интеграция
```bash
# Экспорт метрик для Grafana
curl -s http://localhost:3001/api/metrics | jq '{
  timestamp: .timestamp,
  events_per_second: .data.events.perSecond,
  memory_usage: .data.memory.usage,
  rpc_latency: .data.rpc.avgLatency,
  active_trades: .data.trading.activeTrades
}' >> /var/log/bot_metrics.json
```

---

## 🔧 КАСТОМНЫЕ ENDPOINTS

### Создание собственных endpoints
```typescript
// src/api/routes/custom.ts
import { Router } from 'express';

const router = Router();

// Кастомная аналитика
router.get('/analytics/profit-by-hour', async (req, res) => {
  try {
    const trades = await getTradingHistory();
    const hourlyProfit = calculateHourlyProfit(trades);
    
    res.json({
      success: true,
      data: hourlyProfit
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Топ токены по прибыльности
router.get('/analytics/top-tokens', async (req, res) => {
  const topTokens = await getTopProfitableTokens();
  res.json({ data: topTokens });
});

export default router;
```

---

## 🚨 УСТРАНЕНИЕ ПРОБЛЕМ

### API не отвечает
```bash
# Проверь что бот запущен
curl http://localhost:3001/health

# Проверь порты
netstat -tulpn | grep :3001

# Проверь логи API
tail -f logs/api.log
```

### WebSocket не подключается
```bash
# Проверь WebSocket endpoint
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Key: test" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:3001/ws
```

### Медленные ответы API
```bash
# Проверь нагрузку на систему
curl http://localhost:3001/api/metrics | jq '.data.memory, .data.rpc'

# Увеличь таймауты если нужно
API_TIMEOUT=10000
```

---

## 📈 ЛУЧШИЕ ПРАКТИКИ

### 🎯 Рекомендации по мониторингу:

1. **Настрой алерты** для критических событий
2. **Мониторь ключевые метрики** каждые 30 секунд
3. **Создай dashboard** для визуального контроля
4. **Логируй все API вызовы** для анализа
5. **Используй WebSocket** для real-time обновлений
6. **Настрой backup мониторинг** на случай сбоев

### 🔧 Автоматизация:
- **Cron jobs** для регулярных проверок
- **Telegram/Discord боты** для уведомлений
- **Grafana/Prometheus** для метрик
- **Custom scripts** для специфичной аналитики

---

## 🎉 ЗАКЛЮЧЕНИЕ

API мониторинг предоставляет полный контроль над ботом с возможностью:

- 📊 **Real-time отслеживания** всех операций
- 🔧 **Удаленного управления** и настройки
- 📈 **Детальной аналитики** производительности
- 🛡️ **Системы безопасности** и контроля рисков

**Используй API для создания собственных инструментов мониторинга и автоматизации!** 🚀
