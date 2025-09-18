# 🚀 **SOLANA SNIPER BOT - ПОЛНАЯ ДОКУМЕНТАЦИЯ**

## 📋 **СОДЕРЖАНИЕ**

1. [Введение](#введение)
2. [Быстрый старт](#быстрый-старт)
3. [Установка и настройка](#установка-и-настройка)
4. [Конфигурация](#конфигурация)
5. [Запуск бота](#запуск-бота)
6. [Web Dashboard](#web-dashboard)
7. [API Документация](#api-документация)
8. [Безопасность](#безопасность)
9. [Мониторинг](#мониторинг)
10. [Troubleshooting](#troubleshooting)
11. [FAQ](#faq)

---

## 🎯 **ВВЕДЕНИЕ**

**Solana Sniper Bot** - это высокопроизводительный торговый бот для автоматической торговли новыми токенами на блокчейне Solana. Бот способен обрабатывать **1000+ событий в секунду** и автоматически торговать токенами с продвинутой фильтрацией и управлением рисками.

### ⚡ **КЛЮЧЕВЫЕ ВОЗМОЖНОСТИ:**

- **🎯 Высокая производительность** - 1000+ событий/сек, <50мс латентность
- **🔍 Умное обнаружение токенов** - real-time через onProgramAccountChange
- **🛡️ Продвинутая фильтрация** - 3-этапный pipeline с оптимизацией
- **💰 Автоматическая торговля** - paper и live режимы с TP/SL/TTL
- **🔒 Управление рисками** - circuit breaker, лимиты потерь, контроль экспозиции
- **🌐 Web интерфейс** - профессиональный dashboard с real-time данными
- **🛡️ Безопасность** - многоуровневая защита и аутентификация

---

## 🚀 **БЫСТРЫЙ СТАРТ**

### **1. Клонирование и установка**

```bash
# Клонируем репозиторий
git clone <repository-url>
cd solana-sniper-bot

# Устанавливаем зависимости
npm install

# Создаем конфигурацию
cp .env.example .env
```

### **2. Настройка окружения**

Отредактируйте файл `.env`:

```bash
# КРИТИЧНО: Настройте RPC endpoints (нужно минимум 3)
RPC_ENDPOINT_1=https://api.mainnet-beta.solana.com
RPC_ENDPOINT_2=https://solana-api.projectserum.com
RPC_ENDPOINT_3=https://rpc.ankr.com/solana

# Торговые настройки
PAPER_MODE=true              # ВСЕГДА начинайте с paper mode!
QUOTE_AMOUNT=0.0001          # Сумма SOL на сделку
TAKE_PROFIT=50               # Take profit %
STOP_LOSS=30                 # Stop loss %
```

### **3. Запуск в paper режиме**

```bash
# Сборка проекта
npm run build

# Запуск в безопасном paper режиме
npm run start:paper
```

### **4. Открытие Web Dashboard**

Откройте браузер и перейдите на `http://localhost:3000`

**🎉 ГОТОВО! Бот запущен в безопасном режиме!**

---

## 🔧 **УСТАНОВКА И НАСТРОЙКА**

### **Системные требования:**

- **Node.js** 18+ 
- **npm** 8+
- **2GB RAM** минимум
- **SSD диск** для базы данных
- **Стабильное интернет соединение**

### **Установка через Docker:**

```bash
# Сборка образа
docker build -t solana-sniper-bot .

# Запуск через docker-compose
docker-compose up -d
```

### **Создание директорий:**

```bash
mkdir -p data logs wallets
chmod 700 wallets  # Безопасные права для кошельков
```

### **Настройка кошельков:**

1. Создайте JSON файл кошелька в `./wallets/`
2. Установите права доступа: `chmod 600 ./wallets/wallet.json`
3. Укажите путь в `.env`: `WALLET_PRIVATE_KEY_PATH=./wallets/wallet.json`

**⚠️ ВАЖНО: НИКОГДА не коммитьте приватные ключи в git!**

---

## ⚙️ **КОНФИГУРАЦИЯ**

### **Основные параметры (.env):**

```bash
# === РЕЖИМ РАБОТЫ ===
PAPER_MODE=true                    # true = безопасный режим, false = реальная торговля
NODE_ENV=production               # production/development
LOG_LEVEL=info                    # debug/info/warn/error

# === RPC НАСТРОЙКИ ===
RPC_ENDPOINT_1=https://api.mainnet-beta.solana.com
RPC_ENDPOINT_2=https://solana-api.projectserum.com
RPC_ENDPOINT_3=https://rpc.ankr.com/solana
# Добавьте больше RPC для надежности
RPC_TIMEOUT=3000                  # Таймаут RPC запросов (мс)
RPC_RATE_LIMIT=500               # Лимит запросов в секунду

# === ТОРГОВЫЕ НАСТРОЙКИ ===
QUOTE_AMOUNT=0.0001              # Сумма SOL на сделку
TAKE_PROFIT=50                   # Take profit в %
STOP_LOSS=30                     # Stop loss в %
TTL_MINUTES=30                   # Время жизни позиции в минутах
SLIPPAGE_LIMIT=15               # Максимальный slippage в %

# === ПРОИЗВОДИТЕЛЬНОСТЬ ===
MAX_CONCURRENT_TRADES=25         # Максимум параллельных сделок
MAX_CONCURRENT_FILTERS=50        # Максимум параллельных фильтров
MAX_POSITIONS=100               # Максимум открытых позиций

# === ФИЛЬТРЫ ===
ENABLE_ROUTE_GATE=true          # Включить Jupiter фильтр
ENABLE_ON_CHAIN=true            # Включить on-chain фильтр
ENABLE_DEXSCREENER=true         # Включить DexScreener фильтр
RISK_THRESHOLD=70               # Минимальный score для прохождения

# === БЕЗОПАСНОСТЬ ===
CIRCUIT_BREAKER_MAX_FAILURES=10 # Максимум ошибок подряд
DAILY_LOSS_LIMIT=0.05           # Лимит дневных потерь (SOL)
MAX_EXPOSURE=0.2                # Максимальная экспозиция (SOL)
RESERVE_SOL=0.01                # Резерв для комиссий

# === API ===
API_PORT=3001                   # Порт API сервера
ENABLE_API=true                 # Включить API
CORS_ORIGIN=*                   # CORS настройки
```

### **Настройка фильтров:**

**Route Gate Filter (Jupiter API):**
- Проверяет ликвидность через Jupiter
- Запускается ПЕРВЫМ для оптимизации
- Настройки: `JUPITER_RATE_LIMIT=50`

**On-Chain Filter:**
- Быстрая on-chain валидация
- Проверяет mint authority, freeze authority, supply
- Запускается параллельно с Route Gate

**DexScreener Filter:**
- Проверяет социальные сети и метаданные
- Запускается ТОЛЬКО если другие фильтры прошли
- Настройки: `DEXSCREENER_RATE_LIMIT=100`

---

## 🚀 **ЗАПУСК БОТА**

### **Paper Mode (Безопасный режим):**

```bash
# Development режим с hot reload
npm run dev:paper

# Production режим
npm run start:paper
```

### **Live Mode (Реальная торговля):**

**⚠️ ВНИМАНИЕ: Используйте только после тщательного тестирования!**

```bash
# Убедитесь что настроили кошелек
WALLET_PRIVATE_KEY_PATH=./wallets/your-wallet.json

# Отключите paper mode
PAPER_MODE=false

# Запуск
npm run start:live
```

### **Docker запуск:**

```bash
# Через docker-compose (рекомендуется)
docker-compose up -d

# Прямой запуск Docker
docker run -d --name sniper-bot \
  -p 3001:3001 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/wallets:/app/wallets:ro \
  --env-file .env \
  solana-sniper-bot
```

### **Проверка статуса:**

```bash
# Проверка здоровья
curl http://localhost:3001/health

# Статус бота
curl http://localhost:3001/api/bot/status

# Метрики
curl http://localhost:3001/api/metrics
```

---

## 🌐 **WEB DASHBOARD**

### **Доступ к Dashboard:**

Откройте браузер: `http://localhost:3000`

### **Основные разделы:**

**📊 Dashboard:**
- Статус бота (запущен/остановлен)
- Общий PnL
- Количество открытых позиций
- Системные метрики
- Добавление токенов вручную

**📈 Positions:**
- Таблица всех позиций
- Фильтрация по статусу
- Сортировка по PnL, времени
- Детальная информация по каждой позиции

**💰 Trading:**
- История торговли
- Paper trading управление
- Статистика производительности

**🛡️ Safety:**
- Статус безопасности
- Failed safety checks
- Управление live trading
- Emergency stop контроль

### **Управление ботом:**

- **Start/Stop/Restart** - управление ботом
- **Add Token** - добавить токен для обработки
- **Circuit Breaker Reset** - сброс circuit breaker
- **Live Trading Enable/Disable** - управление live торговлей

### **Real-time обновления:**

Dashboard автоматически получает обновления через WebSocket:
- Статус бота каждые 5 секунд
- Позиции каждые 10 секунд  
- Метрики каждые 15 секунд
- Торговые события в реальном времени

---

## 📡 **API ДОКУМЕНТАЦИЯ**

### **Базовый URL:** `http://localhost:3001/api`

### **Аутентификация:**

Для защищенных endpoints используйте API ключ:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:3001/api/endpoint
```

### **Bot Control (`/api/bot`):**

```bash
# Получить статус бота
GET /api/bot/status

# Запустить бота
POST /api/bot/start

# Остановить бота
POST /api/bot/stop

# Перезапустить бота
POST /api/bot/restart

# Сбросить circuit breaker
POST /api/bot/circuit-breaker/reset

# Добавить токен вручную
POST /api/bot/tokens/add
Content-Type: application/json
{
  "mintAddress": "TokenMintAddress..."
}
```

### **Positions (`/api/positions`):**

```bash
# Все позиции с фильтрацией
GET /api/positions?limit=50&status=active&sortBy=pnl&sortOrder=desc

# Только открытые позиции
GET /api/positions/open

# Конкретная позиция
GET /api/positions/{mintAddress}

# Статистика позиций
GET /api/positions/stats/summary
```

### **Trading (`/api/trading`):**

```bash
# История торговли
GET /api/trading/history?limit=100

# Paper trading (только в paper mode)
GET /api/trading/paper/wallet
GET /api/trading/paper/positions
GET /api/trading/paper/history
GET /api/trading/paper/performance

# Ручная paper торговля
POST /api/trading/paper/buy
{
  "mintAddress": "...",
  "amount": 0.001
}

POST /api/trading/paper/sell
{
  "mintAddress": "...",
  "amount": 1000,
  "reason": "manual"
}

# Сброс paper данных
POST /api/trading/paper/reset
```

### **Metrics (`/api/metrics`):**

```bash
# Все метрики
GET /api/metrics

# Только производительность
GET /api/metrics/performance

# Системные метрики
GET /api/metrics/system
```

### **Wallets (`/api/wallets`):**

```bash
# Все кошельки (безопасная информация)
GET /api/wallets

# Конкретный кошелек
GET /api/wallets/{name}

# Создать новый кошелек (требует admin API key)
POST /api/wallets/create
{
  "name": "new-wallet",
  "encrypt": true
}
```

### **Safety (`/api/safety`):**

```bash
# Статус безопасности
GET /api/safety/status

# Логи безопасности
GET /api/safety/logs?limit=100

# Включить live trading
POST /api/safety/enable-live-trading

# Отключить live trading
POST /api/safety/disable-live-trading
{
  "reason": "Manual disable"
}

# Сбросить emergency stop
POST /api/safety/reset-emergency-stop
```

### **Health Monitoring (`/api/health`):**

```bash
# Общее здоровье системы
GET /api/health

# Краткая сводка
GET /api/health/summary

# История метрики
GET /api/health/metrics/{metricName}?hours=24

# Алерты
GET /api/health/alerts?limit=50&resolved=false

# Разрешить алерт
POST /api/health/alerts/{alertId}/resolve
```

### **Стандартный формат ответов:**

```json
{
  "success": true,
  "data": { ... },
  "timestamp": 1640995200000
}
```

**Ошибки:**

```json
{
  "success": false,
  "error": "Error message",
  "timestamp": 1640995200000
}
```

---

## 🔒 **БЕЗОПАСНОСТЬ**

### **Многоуровневая защита:**

**1. Input Validation:**
- Защита от SQL injection
- Защита от XSS атак
- Защита от path traversal
- Защита от command injection

**2. Rate Limiting:**
- API endpoints: 100 запросов/минуту
- Authentication: 5 попыток/5 минут
- Wallet operations: 10 запросов/минуту
- Trading operations: 50 запросов/минуту

**3. API Key Authentication:**
- Генерация безопасных API ключей
- Permission-based доступ
- Автоматическая ротация ключей

**4. File System Protection:**
- Автоматическая установка прав доступа
- Защита wallet файлов (600 permissions)
- Защита конфигурационных файлов

### **Безопасные практики:**

**✅ DO:**
- Всегда начинайте с PAPER_MODE=true
- Используйте малые суммы для тестирования
- Регулярно проверяйте логи безопасности
- Используйте сильные API ключи
- Делайте резервные копии кошельков

**❌ DON'T:**
- Никогда не коммитьте приватные ключи
- Не отключайте input validation
- Не игнорируйте security alerts
- Не используйте слабые пароли
- Не запускайте с root правами

### **Мониторинг безопасности:**

```bash
# Проверка security events
GET /api/security/events

# Заблокированные IP
GET /api/security/blocked

# Метрики безопасности
GET /api/security/metrics
```

---

## 📊 **МОНИТОРИНГ**

### **Health Monitoring System:**

Бот включает продвинутую систему мониторинга здоровья:

**Системные метрики:**
- Использование памяти
- Загрузка CPU
- Uptime
- Дисковое пространство

**Производительность:**
- События в секунду
- Латентность обработки
- Использование RPC
- Глубина очереди

**Торговые метрики:**
- Общий PnL
- Win rate
- Средний размер сделки
- Открытые позиции

**RPC метрики:**
- Здоровье RPC endpoints
- Средняя латентность
- Количество ошибок

### **Алерты:**

Система автоматически создает алерты при:
- Критическом использовании памяти (>90%)
- Высокой загрузке CPU (>90%)
- Низком здоровье RPC (<50%)
- Активации circuit breaker
- Высоких потерях

### **Prometheus интеграция:**

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'solana-sniper-bot'
    static_configs:
      - targets: ['localhost:9090']
```

### **Grafana Dashboard:**

Импортируйте готовый dashboard для визуализации метрик.

---

## 🔧 **TROUBLESHOOTING**

### **Частые проблемы:**

**1. Бот не запускается:**

```bash
# Проверьте логи
tail -f logs/bot.log

# Проверьте конфигурацию
npm run config

# Проверьте RPC endpoints
curl https://api.mainnet-beta.solana.com -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

**2. Низкая производительность:**

- Добавьте больше RPC endpoints
- Увеличьте MAX_CONCURRENT_FILTERS
- Проверьте использование памяти
- Оптимизируйте настройки кэша

**3. Circuit breaker активируется:**

```bash
# Проверьте причину
GET /api/bot/status

# Проверьте логи ошибок
GET /api/safety/logs

# Сбросьте circuit breaker
POST /api/bot/circuit-breaker/reset
```

**4. RPC проблемы:**

- Проверьте здоровье RPC: `GET /api/metrics`
- Добавьте резервные RPC endpoints
- Увеличьте RPC_TIMEOUT
- Уменьшите RPC_RATE_LIMIT

**5. Проблемы с памятью:**

```bash
# Проверьте использование памяти
GET /api/metrics/system

# Уменьшите размеры кэша
CACHE_TTL_METADATA=60
CACHE_TTL_POOL=30

# Уменьшите лимиты
MAX_POSITIONS=50
MAX_CONCURRENT_TRADES=10
```

### **Логи и диагностика:**

**Структура логов:**

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

**Коды событий:**
- `DETECTED_POOL` - Найден новый пул
- `SKIP_ROUTE_GATE` - Не прошел Route Gate фильтр
- `SKIP_ON_CHAIN` - Не прошел On-Chain фильтр
- `SKIP_DEXSCREENER` - Не прошел DexScreener фильтр
- `BUY_SUCCESS` - Успешная покупка
- `SELL_TP` - Take profit сработал
- `SELL_SL` - Stop loss сработал
- `CIRCUIT_BREAKER` - Circuit breaker активирован

### **Performance Tuning:**

**Для высокой нагрузки:**

```bash
# Увеличьте лимиты
MAX_CONCURRENT_TRADES=50
MAX_CONCURRENT_FILTERS=100
RPC_RATE_LIMIT=1000

# Оптимизируйте кэш
CACHE_TTL_METADATA=600
CACHE_TTL_POOL=120
REDIS_URL=redis://localhost:6379

# Добавьте больше RPC
RPC_ENDPOINT_4=...
RPC_ENDPOINT_5=...
```

---

## ❓ **FAQ**

### **Q: Безопасно ли использовать бота?**

A: Бот включает множество защитных механизмов:
- Paper mode для безопасного тестирования
- Circuit breaker для автоматической остановки
- Лимиты потерь и экспозиции
- Comprehensive error handling

**Всегда начинайте с paper mode и малых сумм!**

### **Q: Какую прибыль можно ожидать?**

A: Прибыль зависит от:
- Рыночных условий
- Настроек фильтров
- Управления рисками
- Качества RPC endpoints

**Нет гарантий прибыли. Торговля криптовалютами связана с высокими рисками.**

### **Q: Сколько RPC endpoints нужно?**

A: Рекомендуется минимум 10 RPC endpoints для:
- Высокой доступности
- Распределения нагрузки
- Резервирования при сбоях

### **Q: Как настроить фильтры?**

A: Настройка фильтров:

```bash
# Включить/отключить фильтры
ENABLE_ROUTE_GATE=true
ENABLE_ON_CHAIN=true
ENABLE_DEXSCREENER=true

# Настроить порог риска
RISK_THRESHOLD=70  # 0-100, выше = строже

# Настроить специфичные параметры
MAX_PRICE_IMPACT=15
MAX_TOP1_HOLDER_PERCENT=20
```

### **Q: Как мониторить производительность?**

A: Используйте:
- Web Dashboard для real-time мониторинга
- API endpoints для метрик
- Health monitoring для алертов
- Логи для детальной диагностики

### **Q: Что делать при ошибках?**

A: Пошаговая диагностика:

1. Проверьте статус: `GET /api/bot/status`
2. Проверьте логи: `tail -f logs/bot.log`
3. Проверьте RPC: `GET /api/metrics`
4. Проверьте safety: `GET /api/safety/status`
5. Сбросьте circuit breaker если нужно

### **Q: Как обновить бота?**

A: Обновление:

```bash
# Остановите бота
npm run stop

# Обновите код
git pull

# Установите зависимости
npm install

# Пересоберите
npm run build

# Запустите
npm run start:paper
```

### **Q: Поддерживаются ли другие блокчейны?**

A: В настоящее время бот поддерживает только Solana. Архитектура позволяет добавить поддержку других блокчейнов в будущем.

---

## 📞 **ПОДДЕРЖКА**

### **Получение помощи:**

1. **Документация** - прочитайте эту документацию полностью
2. **Логи** - проверьте логи для диагностики проблем
3. **API** - используйте API endpoints для получения статуса
4. **Health checks** - мониторьте здоровье системы

### **Сообщение о проблемах:**

При сообщении о проблемах включите:
- Версию бота
- Конфигурацию (без приватных ключей!)
- Логи ошибок
- Шаги для воспроизведения

### **Безопасность:**

**⚠️ НИКОГДА не делитесь:**
- Приватными ключами кошельков
- API ключами
- Seed фразами
- Конфиденциальной информацией

---

## 📄 **ЛИЦЕНЗИЯ**

MIT License - см. файл LICENSE для деталей.

---

## ⚠️ **ДИСКЛЕЙМЕР**

- **🚨 ВЫСОКИЙ РИСК**: Торговля криптовалютами связана с существенными рисками
- **💰 ВОЗМОЖНОСТЬ ПОТЕРЬ**: Вы можете потерять все инвестированные средства
- **🔬 ЭКСПЕРИМЕНТАЛЬНОЕ ПО**: Это бета-версия с возможными багами
- **📚 ОБРАЗОВАТЕЛЬНЫЕ ЦЕЛИ**: Предназначено для образовательных целей
- **🔒 ВАША ОТВЕТСТВЕННОСТЬ**: Всегда проверяйте настройки перед торговлей
- **⚖️ БЕЗ ГАРАНТИЙ**: ПО предоставляется как есть без гарантий

---

**🚀 УДАЧНОЙ ТОРГОВЛИ! ПОМНИТЕ О РИСКАХ!**

*Документация обновлена: 2025*