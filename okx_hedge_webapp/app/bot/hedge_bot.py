
import math
import time
from sys import stdout
from datetime import datetime

from loguru import logger

from . import hedge_config as config
from . import okx_api

# --- Конфигурация логгера ---
logger.remove()
logger.add(stdout, level="INFO")
logger.add("logs/hedge_bot_log_{time}.log", rotation="10 MB", level="DEBUG")

class Position:
    """Класс для хранения состояния одной позиции (long или short)."""
    def __init__(self, side):
        self.side = side
        self._reset()

    def _reset(self):
        self.is_cycle_active = False
        self.avg_entry_price = 0.0
        self.total_position_qty = 0.0
        self.executed_orders_count = 0
        self.last_execution_price = 0.0
        self.active_tp_order_id = None
        self.pending_orders = {}  # {order_id: order_size}
        self.cycle_start_time = None
        self.total_used_margin = 0.0

class HedgeTradingBot:
    """Основной класс бота для хеджирующей стратегии."""
    def __init__(self):
        self.positions = {}
        if config.LONG_ENABLED:
            self.positions['long'] = Position('long')
        if config.SHORT_ENABLED:
            self.positions['short'] = Position('short')
        
        self.tick_size = 0.0
        self.lot_size = 0.0
        self.min_size = 0.0
        # Распределяем баланс поровну, если обе стратегии включены
        self.balance_allocation = 0.5 if (config.LONG_ENABLED and config.SHORT_ENABLED) else 1.0

    def run(self):
        self._initialize_bot()
        while True:
            try:
                for side, position in self.positions.items():
                    if not position.is_cycle_active:
                        self._start_new_cycle(side)
                    else:
                        self._check_orders_status(side)
                time.sleep(config.BOT_POLL_INTERVAL)
            except KeyboardInterrupt:
                logger.warning("Бот остановлен пользователем.")
                break
            except Exception as e:
                logger.error(f"Произошла непредвиденная ошибка: {e}")
                time.sleep(config.BOT_POLL_INTERVAL)

    def _initialize_bot(self):
        logger.info("Инициализация настроек бота...")
        logger.warning("Убедитесь, что в настройках OKX включен Hedge Mode!")
        okx_api.set_leverage(config.TRADING_PAIR, config.LEVERAGE)
        logger.info(f"Плечо установлено на {config.LEVERAGE}x для {config.TRADING_PAIR}")

        instrument_info = okx_api.get_instrument_details(config.TRADING_PAIR)
        if instrument_info and instrument_info.get('data'):
            data = instrument_info['data'][0]
            self.tick_size = float(data.get('tickSz', 0.0))
            self.lot_size = float(data.get('lotSz', 0.0))
            self.min_size = float(data.get('minSz', 0.0))
            # Определяем количество знаков после запятой для корректного форматирования
            self.tick_size_decimals = len(str(self.tick_size).split('.')[1]) if '.' in str(self.tick_size) else 0
            self.lot_size_decimals = len(str(self.lot_size).split('.')[1]) if '.' in str(self.lot_size) else 0
            logger.info(f"Правила торговли: Tick Size={self.tick_size}, Lot Size={self.lot_size}, Min Size={self.min_size}")
        else:
            logger.error("Не удалось получить детали инструмента. Выход.")
            exit()

    def _start_new_cycle(self, side):
        position = self.positions[side]
        logger.info(f"[{side.upper()}] Начинаем новый торговый цикл...")

        balance = okx_api.get_account_balance()
        if not balance or not balance.get('data'):
            logger.error(f"[{side.upper()}] Не удалось получить баланс.")
            return
        
        usdt_balance = next((d.get('availEq', 0) for d in balance['data'][0]['details'] if d['ccy'] == 'USDT'), 0)
        allocated_balance = float(usdt_balance) * self.balance_allocation
        logger.info(f"[{side.upper()}] Доступный баланс USDT (выделено {self.balance_allocation*100}%): {allocated_balance:.2f}")

        ticker = okx_api.get_ticker(config.TRADING_PAIR)
        if not ticker or not ticker.get('data'):
            logger.error(f"[{side.upper()}] Не удалось получить цену тикера.")
            return
        current_price = float(ticker['data'][0]['last'])
        logger.info(f"[{side.upper()}] Текущая цена: {current_price}")

        margin_perc = getattr(config, f"{side.upper()}_MARGIN_PER_ORDER_PERCENTAGE")
        margin = allocated_balance * margin_perc
        order_size = self._adjust_size(max(self.min_size, (margin * config.LEVERAGE) / current_price))
        logger.info(f"[{side.upper()}] Расчетный размер первого ордера: {order_size} (маржа: ${margin:.2f})")

        order_side = 'buy' if side == 'long' else 'sell'
        result = okx_api.place_order(instId=config.TRADING_PAIR, side=order_side, ordType='limit', sz=self._format_size(order_size), px=self._format_price(current_price), posSide=side)
        
        if result and result.get('data')[0]['sCode'] == '0':
            order_id = result['data'][0]['ordId']
            position.is_cycle_active = True
            position.pending_orders[order_id] = order_size
            position.last_execution_price = current_price
            position.total_used_margin += margin
            position.cycle_start_time = datetime.now()
            logger.success(f"[{side.upper()}] Первый ордер ({order_side}) успешно размещен. ID: {order_id}")
        else:
            logger.error(f"[{side.upper()}] Ошибка размещения первого ордера: {result.get('data')[0]['sMsg']}")

    def _check_orders_status(self, side):
        position = self.positions[side]
        # Проверяем, не завис ли ПЕРВЫЙ ордер (только если позиция еще пустая)
        if (position.executed_orders_count == 0 and 
            position.total_position_qty == 0 and 
            (datetime.now() - position.cycle_start_time).total_seconds() > 30):
            logger.warning(f"[{side.upper()}] Первый ордер не исполнен за 30 секунд. Отменяем и начинаем заново...")
            # Отменяем только первый ордер (когда позиция пустая)
            if position.pending_orders:
                okx_api.cancel_multiple_orders(config.TRADING_PAIR, list(position.pending_orders.keys()))
            position._reset() # Сбрасываем для рестарта цикла
            return # Выходим, чтобы на следующей итерации начался новый цикл

        for order_id in list(position.pending_orders.keys()):
            details = okx_api.get_order_details(config.TRADING_PAIR, order_id)
            state = details['data'][0].get('state')
            if state == 'filled':
                self._handle_filled_order(side, details['data'][0])

        if position.active_tp_order_id:
            details = okx_api.get_order_details(config.TRADING_PAIR, position.active_tp_order_id)
            if details and details.get('data'):
                tp_state = details['data'][0].get('state')
                if tp_state == 'filled':
                    self._handle_filled_tp_order(side, details['data'][0])

    def _handle_filled_order(self, side, details):
        position = self.positions[side]
        order_id, avg_price, filled_size = details['ordId'], float(details['avgPx']), float(details['accFillSz'])
        logger.info(f"[{side.upper()}] Исполнен ордер {order_id}: Размер={filled_size}, Цена={avg_price}")

        if position.active_tp_order_id:
            okx_api.cancel_order(config.TRADING_PAIR, position.active_tp_order_id)

        new_qty = position.total_position_qty + filled_size
        position.avg_entry_price = ((position.avg_entry_price * position.total_position_qty) + (avg_price * filled_size)) / new_qty
        position.total_position_qty = new_qty
        position.executed_orders_count += 1
        position.last_execution_price = avg_price
        if order_id in position.pending_orders: del position.pending_orders[order_id]
        logger.info(f"[{side.upper()}] Новое состояние: Сред. цена={position.avg_entry_price:.4f}, Объем={position.total_position_qty:.4f}")

        tp_perc = getattr(config, f"{side.upper()}_TAKE_PROFIT_PERCENTAGE")
        tp_price = self._adjust_price(position.avg_entry_price * (1 + tp_perc if side == 'long' else 1 - tp_perc))
        tp_side = 'sell' if side == 'long' else 'buy'

        # Пытаемся разместить TP ордер с повторными попытками
        tp_order_placed = False
        for attempt in range(1, 4):
            logger.info(f"[{side.upper()}] Размещение TP ордера по цене {tp_price} (Попытка {attempt}/3)")
            tp_res = okx_api.place_order(instId=config.TRADING_PAIR, side=tp_side, sz=self._format_size(position.total_position_qty), px=self._format_price(tp_price), posSide=side, ordType='limit')
            if tp_res and tp_res.get('data') and tp_res['data'][0].get('sCode') == '0':
                position.active_tp_order_id = tp_res['data'][0]['ordId']
                logger.success(f"[{side.upper()}] Новый TP ордер успешно размещен. ID: {position.active_tp_order_id}")
                tp_order_placed = True
                break
            else:
                error_message = "No response from API"
                if tp_res and isinstance(tp_res.get('data'), list) and tp_res['data']:
                    error_message = tp_res['data'][0].get('sMsg', 'No error message from API')
                logger.warning(f"[{side.upper()}] Попытка {attempt} не удалась: {error_message}")
                if attempt < 3:
                    time.sleep(3)

        if not tp_order_placed:
            logger.error(f"[{side.upper()}] КРИТИЧНО: Не удалось разместить TP ордер после 3 попыток!")

        if position.executed_orders_count < config.MAX_ORDERS_IN_CYCLE:
            entry_perc = getattr(config, f"{side.upper()}_ENTRY_PRICE_{'FALL' if side == 'long' else 'RISE'}_PERCENTAGE")
            next_price = self._adjust_price(position.last_execution_price * (1 - entry_perc if side == 'long' else 1 + entry_perc))
            next_size = self._adjust_size(filled_size)
            position.total_used_margin += (next_size * next_price) / config.LEVERAGE
            
            next_side = 'buy' if side == 'long' else 'sell'
            next_res = okx_api.place_order(instId=config.TRADING_PAIR, side=next_side, sz=self._format_size(next_size), px=self._format_price(next_price), posSide=side, ordType='limit')
            if next_res and next_res.get('data')[0]['sCode'] == '0':
                logger.success(f"[{side.upper()}] Следующий усредняющий ордер размещен. ID: {next_res['data'][0]['ordId']}")
                position.pending_orders[next_res['data'][0]['ordId']] = next_size
            else:
                logger.error(f"[{side.upper()}] Не удалось разместить следующий усредняющий ордер.")


    def _handle_filled_tp_order(self, side, details):
        position = self.positions[side]
        exit_price = float(details.get('avgPx', 0))
        profit = (exit_price - position.avg_entry_price if side == 'long' else position.avg_entry_price - exit_price) * position.total_position_qty
        logger.success(f"[{side.upper()}] ЦИКЛ ЗАВЕРШЕН | Прибыль: {profit:.2f} USDT")
        
        if position.pending_orders:
            okx_api.cancel_multiple_orders(config.TRADING_PAIR, list(position.pending_orders.keys()))
        
        position._reset()
        logger.info(f"[{side.upper()}] Состояние сброшено. Готов к новому циклу.")

    def _adjust_price(self, price):
        """Округляет цену до ближайшего значения, кратного шагу тика."""
        return round(price / self.tick_size) * self.tick_size

    def _adjust_size(self, size):
        """Округляет размер до ближайшего значения, кратного размеру лота."""
        return round(size / self.lot_size) * self.lot_size

    def _format_price(self, price):
        """Форматирует цену в строку с правильным количеством десятичных знаков."""
        return f"{price:.{self.tick_size_decimals}f}"

    def _format_size(self, size):
        """Форматирует размер в строку с правильным количеством десятичных знаков."""
        return f"{size:.{self.lot_size_decimals}f}"

