
API_KEY = "" # YOUR_API_KEY
API_SECRET_KEY = "" # YOUR_SECRET_KEY
API_PASSPHRASE = "" # YOUR_PASSPHRASE

TRADING_PAIR = "ETH-USDT-SWAP"
LEVERAGE = 100

# === Общие настройки для обеих стратегий ===
DRY_RUN_MODE = True  # True для симуляции, False для реальной торговли
BOT_POLL_INTERVAL = 5  # Интервал опроса в секундах
MAX_ORDERS_IN_CYCLE = 5  # Максимальное количество усредняющих ордеров

# === Настройки для LONG стратегии ===
LONG_ENABLED = True
LONG_MARGIN_PER_ORDER_PERCENTAGE = 0.1  # 5% от баланса на первый ордер
LONG_TAKE_PROFIT_PERCENTAGE = 0.001  # 0.1%
LONG_ENTRY_PRICE_FALL_PERCENTAGE = 0.005  # 0.5% падения для усреднения

# === Настройки для SHORT стратегии ===
SHORT_ENABLED = True
SHORT_MARGIN_PER_ORDER_PERCENTAGE = 0.1  # 5% от баланса на первый ордер
SHORT_TAKE_PROFIT_PERCENTAGE = 0.001  # 0.1%
SHORT_ENTRY_PRICE_RISE_PERCENTAGE = 0.005  # 0.5% роста для усреднения

