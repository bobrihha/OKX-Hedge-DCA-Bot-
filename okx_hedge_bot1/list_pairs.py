# -*- coding: utf-8 -*-
import okx_api
import json

def get_swap_pairs():
    """Запрашивает и выводит все доступные торговые пары SWAP с биржи OKX."""
    print("Запрашиваю список всех SWAP пар с OKX...")

    # Эндпоинт для получения информации об инструментах
    path = "/api/v5/public/instruments?instType=SWAP"
    
    # Используем существующую функцию для запроса. 
    # Публичные эндпоинты не требуют авторизации, но передача ключей не вызовет ошибки.
    response = okx_api.make_request('GET', path)

    if response and response.get('code') == '0':
        pairs = response.get('data', [])
        if not pairs:
            print("Не удалось найти доступные пары. Ответ API пуст.")
            return

        print("\n--- Список доступных торговых пар (SWAP) для конфигурации ---")
        for pair in pairs:
            inst_id = pair.get('instId')
            # Выводим только пары к USDT для удобства, т.к. они самые популярные
            if 'USDT' in inst_id:
                print(inst_id)
        
        print("\n------------------------------------------------------------")
        print("Скопируйте нужное название и вставьте в hedge_config.py")
        print("Например: TRADING_PAIR = \"BTC-USDT-SWAP\"")

    else:
        print("\nНе удалось получить список пар. Ответ от API:")
        # Выводим ответ от API для диагностики
        print(json.dumps(response, indent=2))

if __name__ == "__main__":
    get_swap_pairs()

