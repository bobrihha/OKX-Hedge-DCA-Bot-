# OKX Хеджирующий Торговый Бот

## 1. Описание

Этот торговый бот предназначен для автоматической торговли на криптовалютной бирже OKX с использованием хеджирующей стратегии. Стратегия заключается в одновременном удержании позиций в LONG (на покупку) и SHORT (на продажу) по одной и той же торговой паре (например, `ETH-USDT-SWAP`). Это позволяет извлекать прибыль как при росте, так и при падении рынка.

### Принцип работы:

1.  **Инициализация**: При запуске бот считывает конфигурацию, устанавливает указанное кредитное плечо и получает информацию о торговом инструменте (размер тика, лота).
2.  **Двойной старт**: Если включены обе стратегии (LONG и SHORT), бот начинает два параллельных торговых цикла.
3.  **Первый ордер**: В каждом цикле бот размещает первый лимитный ордер (на покупку для LONG, на продажу для SHORT) на основе текущей рыночной цены и процента от выделенного баланса.
4.  **Усреднение**: Если цена движется против открытой позиции (падает для LONG, растет для SHORT), бот автоматически размещает дополнительные ордера для усреднения точки входа. Это позволяет закрыть позицию в плюс даже при небольшом откате цены. Количество усредняющих ордеров ограничено параметром `MAX_ORDERS_IN_CYCLE`.
5.  **Take-Profit**: После каждого исполненного ордера (первого или усредняющего) бот отменяет старый Take-Profit ордер (если он был) и выставляет новый, рассчитанный на основе новой средней цены входа и заданного процента прибыли (`TAKE_PROFIT_PERCENTAGE`).
6.  **Завершение цикла**: Когда Take-Profit ордер исполняется, цикл считается завершенным. Бот фиксирует прибыль, отменяет все оставшиеся усредняющие ордера для этой позиции и начинает новый торговый цикл.
7.  **Симуляция**: Бот поддерживает режим симуляции (`DRY_RUN_MODE`). В этом режиме он выполняет все те же действия, но не отправляет реальные торговые приказы на биржу, что позволяет безопасно тестировать стратегию.

## 2. Конфигурация

Все настройки бота находятся в файле `hedge_config.py`.

### Основные параметры:

*   `API_KEY`, `API_SECRET_KEY`, `API_PASSPHRASE`: Ваши учетные данные API от биржи OKX. **Это секретная информация, не делитесь ей ни с кем.**
*   `TRADING_PAIR`: Торговая пара для торговли, например, `"ETH-USDT-SWAP"`.
*   `LEVERAGE`: Кредитное плечо.
*   `DRY_RUN_MODE`: `True` для режима симуляции, `False` для реальной торговли.

### Параметры стратегий:

*   `LONG_ENABLED`, `SHORT_ENABLED`: `True` или `False` для включения/отключения соответствующей стратегии.
*   `*_MARGIN_PER_ORDER_PERCENTAGE`: Процент от доступного баланса, используемый для маржи на каждый ордер.
*   `*_TAKE_PROFIT_PERCENTAGE`: Процент прибыли для закрытия позиции.
*   `*_ENTRY_PRICE_*_PERCENTAGE`: Процент изменения цены для размещения усредняющего ордера.
*   `MAX_ORDERS_IN_CYCLE`: Максимальное количество усредняющих ордеров в одном цикле.
*   `BOT_POLL_INTERVAL`: Интервал в секундах, с которым бот проверяет состояние ордеров.

## 3. Установка и Запуск

### Предварительные требования:

1.  Установленный Python 3.
2.  Установленные библиотеки. Если у вас их нет, установите командой:
    ```bash
    pip install requests loguru
    ```
3.  **Важно:** В настройках вашего аккаунта на бирже OKX должен быть включен **"Hedge Mode"** (Режим хеджирования) для торговли деривативами.

### Запуск:

Для запуска бота используйте следующую команду в терминале, находясь в директории с файлами бота:

```bash
python3 hedge_main.py
```

Бот начнет свою работу и будет выводить информацию о своих действиях (логи) в консоль, а также сохранять их в файл в директории `logs`.

### Остановка:

Для штатной остановки бота нажмите комбинацию клавиш `Ctrl+C` в терминале, где он запущен. Бот получит сигнал, выведет сообщение "Бот остановлен пользователем." и завершит свою работу. **Не закрывайте окно терминала просто так, используйте `Ctrl+C` для корректного завершения.**

## 4. Важные замечания

*   **Изменение конфигурации:** Бот считывает настройки из `hedge_config.py` только в момент своего запуска. Если вы измените конфигурацию, когда бот уже работает, новые настройки **не будут применены**. Чтобы они вступили в силу, вам необходимо **остановить бота (`Ctrl+C`) и запустить его заново**.
*   **Риски:** Торговля с кредитным плечом сопряжена с высокими рисками и может привести к потере всего вашего депозита. Используйте бота на свой страх и риск. Настоятельно рекомендуется сначала протестировать его в режиме симуляции (`DRY_RUN_MODE = True`).

обозначения торговых пар для файла конфигурации 
--- Список доступных торговых пар (SWAP) для конфигурации ---
BTC-USDT-SWAP
ETH-USDT-SWAP
SOL-USDT-SWAP
DOGE-USDT-SWAP
XRP-USDT-SWAP
BCH-USDT-SWAP
LTC-USDT-SWAP
PEPE-USDT-SWAP
1INCH-USDT-SWAP
AAVE-USDT-SWAP
ACT-USDT-SWAP
ADA-USDT-SWAP
AI16Z-USDT-SWAP
AIDOGE-USDT-SWAP
ALGO-USDT-SWAP
ARB-USDT-SWAP
ATOM-USDT-SWAP
AUCTION-USDT-SWAP
AVAX-USDT-SWAP
AXS-USDT-SWAP
BABY-USDT-SWAP
BAL-USDT-SWAP
BAND-USDT-SWAP
BNB-USDT-SWAP
BNT-USDT-SWAP
BOME-USDT-SWAP
BRETT-USDT-SWAP
CATI-USDT-SWAP
CAT-USDT-SWAP
CELO-USDT-SWAP
CETUS-USDT-SWAP
CFX-USDT-SWAP
CHZ-USDT-SWAP
COMP-USDT-SWAP
CRO-USDT-SWAP
CRV-USDT-SWAP
DOGS-USDT-SWAP
DOT-USDT-SWAP
EGLD-USDT-SWAP
ETC-USDT-SWAP
ETHW-USDT-SWAP
ETHFI-USDT-SWAP
FIL-USDT-SWAP
FLOKI-USDT-SWAP
FLOW-USDT-SWAP
GMT-USDT-SWAP
HBAR-USDT-SWAP
HMSTR-USDT-SWAP
ICP-USDT-SWAP
ID-USDT-SWAP
IMX-USDT-SWAP
INJ-USDT-SWAP
IOTA-USDT-SWAP
IP-USDT-SWAP
KAITO-USDT-SWAP
KNC-USDT-SWAP
KSM-USDT-SWAP
LDO-USDT-SWAP
LINK-USDT-SWAP
LPT-USDT-SWAP
LQTY-USDT-SWAP
LRC-USDT-SWAP
MAGIC-USDT-SWAP
MAJOR-USDT-SWAP
MASK-USDT-SWAP
MINA-USDT-SWAP
MKR-USDT-SWAP
MSN-USDT-SWAP
NEAR-USDT-SWAP
NEO-USDT-SWAP
NOT-USDT-SWAP
OP-USDT-SWAP
ORBS-USDT-SWAP
PARTI-USDT-SWAP
PENGU-USDT-SWAP
POL-USDT-SWAP
QTUM-USDT-SWAP
SAND-USDT-SWAP
SATS-USDT-SWAP
SCR-USDT-SWAP
SHELL-USDT-SWAP
SHIB-USDT-SWAP
SOLV-USDT-SWAP
SUI-USDT-SWAP
SUSHI-USDT-SWAP
THETA-USDT-SWAP
TON-USDT-SWAP
TRX-USDT-SWAP
UNI-USDT-SWAP
USDC-USDT-SWAP
XLM-USDT-SWAP
XTZ-USDT-SWAP
YFI-USDT-SWAP
YGG-USDT-SWAP
ZETA-USDT-SWAP
ZIL-USDT-SWAP
TESTING-USDT-SWAP

------------------------------------------------------------
Скопируйте нужное название и вставьте в hedge_config.py
Например: TRADING_PAIR = "BTC-USDT-SWAP"
