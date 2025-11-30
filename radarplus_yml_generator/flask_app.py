#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RadarPlus YML Generator
Генерация YML файла для выгрузки товаров на Пульс Цен
"""

import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, render_template_string, Response, jsonify
import re
from html import unescape
import threading
import time
import schedule

app = Flask(__name__)

# Конфигурация
CONFIG = {
    'DIRECTUS_BASE_URL': 'http://radarplus.shop:8055',
    'DIRECTUS_API_TOKEN': 'QpgKB5EhHOIlbElAfQ_SDwxmOEFJMEQ1',  # Ваш API токен
    'YML_FILE_PATH': '/tmp/radarplus_export.yml',
    'SHOP_NAME': 'RadarPlus',
    'SHOP_COMPANY': 'RadarPlus Shop',
    'SHOP_URL': 'https://radarplus.shop',
    'CURRENCY': 'UAH',
    'UPDATE_INTERVAL_HOURS': 6
}

# Глобальные переменные для статуса
app_status = {
    'last_generation': None,
    'file_exists': False,
    'generation_in_progress': False,
    'error_message': None
}

def clean_html(text):
    """Очистка HTML тегов и специальных символов"""
    if not text:
        return ""
    
    # Убираем HTML теги
    clean = re.sub('<.*?>', '', str(text))
    
    # Декодируем HTML сущности
    clean = unescape(clean)
    
    # Заменяем переносы строк на пробелы
    clean = re.sub(r'\s+', ' ', clean)
    
    # Экранируем XML символы
    clean = clean.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    return clean.strip()

def get_directus_data(endpoint, params=None):
    """Получение данных из Directus API"""
    url = f"{CONFIG['DIRECTUS_BASE_URL']}/items/{endpoint}"
    headers = {
        'Authorization': f"Bearer {CONFIG['DIRECTUS_API_TOKEN']}"
    }
    
    if params is None:
        params = {}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при получении данных из {endpoint}: {e}")
        return None

def generate_yml():
    """Генерация YML файла"""
    global app_status
    
    try:
        app_status['generation_in_progress'] = True
        app_status['error_message'] = None
        
        print("Начинаем генерацию YML файла...")
        
        # Получаем категории
        print("Получаем категории...")
        categories_data = get_directus_data('categories', {'limit': -1})
        categories = {}
        if categories_data and 'data' in categories_data:
            for cat in categories_data['data']:
                categories[cat['id']] = clean_html(cat.get('name', ''))
        
        # Получаем товары с вариантами
        print("Получаем товары...")
        products_data = get_directus_data('products', {
            'limit': -1,
            'fields': 'id,name,description,specification,status,category,product_variants.*'
        })
        
        if not products_data or 'data' not in products_data:
            raise Exception("Не удалось получить данные о товарах")
        
        # Создаем YML структуру
        root = ET.Element("yml_catalog")
        root.set("date", datetime.now().strftime("%Y-%m-%d %H:%M"))
        
        shop = ET.SubElement(root, "shop")
        
        # Информация о магазине
        ET.SubElement(shop, "name").text = CONFIG['SHOP_NAME']
        ET.SubElement(shop, "company").text = CONFIG['SHOP_COMPANY']
        ET.SubElement(shop, "url").text = CONFIG['SHOP_URL']
        
        # Валюты
        currencies = ET.SubElement(shop, "currencies")
        currency = ET.SubElement(currencies, "currency")
        currency.set("id", CONFIG['CURRENCY'])
        currency.set("rate", "1")
        
        # Категории
        categories_xml = ET.SubElement(shop, "categories")
        for cat_id, cat_name in categories.items():
            category = ET.SubElement(categories_xml, "category")
            category.set("id", str(cat_id))
            if cat_name:
                category.text = cat_name
        
        # Добавляем категорию по умолчанию
        default_category = ET.SubElement(categories_xml, "category")
        default_category.set("id", "None")
        
        # Товары
        offers = ET.SubElement(shop, "offers")
        offers_count = 0
        
        for product in products_data['data']:
            if product.get('status') != 'published':
                continue
                
            product_name = clean_html(product.get('name', ''))
            product_description = clean_html(product.get('description', ''))
            product_specification = clean_html(product.get('specification', ''))
            category_id = product.get('category') or 'None'
            
            # Объединяем описание и спецификацию
            full_description = f"{product_description} {product_specification}".strip()
            
            # Обрабатываем варианты товара
            variants = product.get('product_variants', [])
            if not variants:
                # Если нет вариантов, создаем базовый товар
                variants = [{'id': 'default', 'price': 0, 'model': ''}]
            
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                    
                variant_id = variant.get('id', 'default')
                price = variant.get('price', 0)
                model = clean_html(variant.get('model', ''))
                
                if price <= 0:
                    continue
                
                # Создаем offer
                offer = ET.SubElement(offers, "offer")
                offer_id = f"{category_id}-{variant_id}"
                offer.set("id", offer_id)
                offer.set("available", "true")
                
                # Название товара
                full_name = f"{product_name} - {model}" if model else product_name
                ET.SubElement(offer, "name").text = full_name
                
                # URL товара
                product_url = f"{CONFIG['SHOP_URL']}/product/{category_id}/variant/{variant_id}"
                ET.SubElement(offer, "url").text = product_url
                
                # Цена
                ET.SubElement(offer, "price").text = str(int(price))
                
                # Валюта
                ET.SubElement(offer, "currencyId").text = CONFIG['CURRENCY']
                
                # Описание
                if full_description:
                    ET.SubElement(offer, "description").text = full_description
                
                offers_count += 1
        
        # Сохраняем файл
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(CONFIG['YML_FILE_PATH'], encoding='utf-8', xml_declaration=True)
        
        # Обновляем статус
        app_status['last_generation'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        app_status['file_exists'] = os.path.exists(CONFIG['YML_FILE_PATH'])
        app_status['generation_in_progress'] = False
        
        print(f"YML файл успешно сгенерирован! Товаров: {offers_count}")
        return True
        
    except Exception as e:
        app_status['error_message'] = str(e)
        app_status['generation_in_progress'] = False
        print(f"Ошибка при генерации YML: {e}")
        return False

def auto_update():
    """Автоматическое обновление файла"""
    schedule.every(CONFIG['UPDATE_INTERVAL_HOURS']).hours.do(generate_yml)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# HTML шаблон
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RadarPlus YML Generator</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .status { padding: 15px; border-radius: 5px; margin: 20px 0; }
        .status.success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        .status.error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .status.warning { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }
        .btn { display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; border: none; cursor: pointer; margin: 5px; }
        .btn:hover { background: #0056b3; }
        .btn.success { background: #28a745; }
        .btn.success:hover { background: #1e7e34; }
        .info-section { margin: 20px 0; padding: 15px; background: #e9ecef; border-radius: 5px; }
        .links { margin-top: 20px; }
        .links a { display: block; margin: 5px 0; color: #007bff; }
        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 RadarPlus YML Generator</h1>
        
        <div class="info-section">
            <h3>📋 Информация о сервисе</h3>
            <p><strong>Цель:</strong> Автоматическая генерация YML файла для выгрузки товаров с сайта RadarPlus на Пульс Цен</p>
            <p><strong>Источник данных:</strong> Directus API ({{ directus_url }})</p>
            <p><strong>Обновление:</strong> По запросу или автоматически</p>
        </div>

        <div class="info-section">
            <h3>📊 Статус системы</h3>
            <p><strong>Последняя генерация:</strong> {{ last_generation or 'Не выполнялась' }}</p>
            
            {% if generation_in_progress %}
                <div class="status warning">⏳ Генерация файла в процессе...</div>
            {% elif error_message %}
                <div class="status error">❌ Ошибка: {{ error_message }}</div>
            {% elif file_exists %}
                <div class="status success">✅ YML файл доступен</div>
            {% else %}
                <div class="status warning">⚠️ YML файл не найден</div>
            {% endif %}
        </div>

        <div style="text-align: center; margin: 30px 0;">
            {% if file_exists %}
                <a href="/yml" class="btn success">📥 Скачать YML файл</a>
            {% endif %}
            <button onclick="generateYml()" class="btn" {% if generation_in_progress %}disabled{% endif %}>
                🔄 Сгенерировать заново
            </button>
        </div>

        <div class="info-section">
            <h3>📊 Статус API</h3>
            <div id="api-status">Проверяем...</div>
        </div>

        <div class="links">
            <h3>🔗 Полезные ссылки</h3>
            <a href="/yml" target="_blank">Прямая ссылка на YML файл</a>
            <a href="/api/status" target="_blank">API статус (JSON)</a>
            <a href="{{ shop_url }}" target="_blank">Сайт RadarPlus</a>
            <a href="https://puls-cen.ru" target="_blank">Пульс Цен</a>
        </div>

        <div class="info-section">
            <h3>⚙️ Инструкции по использованию</h3>
            <p><strong>Для Пульс Цен:</strong> Используйте ссылку <code>{{ base_url }}/yml</code> в настройках выгрузки</p>
            <p><strong>Автоматическое обновление:</strong> Файл обновляется каждые {{ update_interval }} часов</p>
            <p><strong>Ручное обновление:</strong> Используйте кнопку "Сгенерировать заново"</p>
            <p><strong>Мониторинг:</strong> Проверяйте статус через API или веб-интерфейс</p>
        </div>
    </div>

    <script>
        function generateYml() {
            const btn = event.target;
            btn.disabled = true;
            btn.innerHTML = '⏳ Генерируем...';
            
            fetch('/generate', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert('Ошибка: ' + data.error);
                        btn.disabled = false;
                        btn.innerHTML = '🔄 Сгенерировать заново';
                    }
                })
                .catch(error => {
                    alert('Ошибка: ' + error);
                    btn.disabled = false;
                    btn.innerHTML = '🔄 Сгенерировать заново';
                });
        }

        // Проверка статуса API
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                const statusDiv = document.getElementById('api-status');
                if (data.api_accessible) {
                    statusDiv.innerHTML = '<div class="status success">✅ API доступен</div>';
                } else {
                    statusDiv.innerHTML = '<div class="status error">❌ API недоступен: ' + data.error + '</div>';
                }
            })
            .catch(error => {
                document.getElementById('api-status').innerHTML = '<div class="status error">❌ Ошибка проверки API</div>';
            });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Главная страница"""
    return render_template_string(HTML_TEMPLATE, 
                                  last_generation=app_status['last_generation'],
                                  file_exists=app_status['file_exists'],
                                  generation_in_progress=app_status['generation_in_progress'],
                                  error_message=app_status['error_message'],
                                  directus_url=CONFIG['DIRECTUS_BASE_URL'],
                                  shop_url=CONFIG['SHOP_URL'],
                                  base_url=f"http://localhost:8080",  # Замените на ваш домен
                                  update_interval=CONFIG['UPDATE_INTERVAL_HOURS'])

@app.route('/yml')
def download_yml():
    """Скачивание YML файла"""
    if not os.path.exists(CONFIG['YML_FILE_PATH']):
        return "YML файл не найден. Сгенерируйте его сначала.", 404
    
    with open(CONFIG['YML_FILE_PATH'], 'r', encoding='utf-8') as f:
        content = f.read()
    
    return Response(content, 
                   mimetype='application/xml',
                   headers={'Content-Disposition': 'attachment; filename=radarplus_export.yml'})

@app.route('/generate', methods=['POST'])
def generate_yml_endpoint():
    """Генерация YML файла по запросу"""
    if app_status['generation_in_progress']:
        return jsonify({'success': False, 'error': 'Генерация уже в процессе'})
    
    # Запускаем генерацию в отдельном потоке
    threading.Thread(target=generate_yml, daemon=True).start()
    
    return jsonify({'success': True, 'message': 'Генерация запущена'})

@app.route('/api/status')
def api_status():
    """API статус"""
    # Проверяем доступность Directus API
    try:
        response = requests.get(f"{CONFIG['DIRECTUS_BASE_URL']}/server/info", timeout=5)
        api_accessible = response.status_code == 200
        api_error = None
    except Exception as e:
        api_accessible = False
        api_error = str(e)
    
    return jsonify({
        'last_generation': app_status['last_generation'],
        'file_exists': app_status['file_exists'],
        'generation_in_progress': app_status['generation_in_progress'],
        'error_message': app_status['error_message'],
        'api_accessible': api_accessible,
        'api_error': api_error,
        'config': {
            'directus_url': CONFIG['DIRECTUS_BASE_URL'],
            'update_interval': CONFIG['UPDATE_INTERVAL_HOURS']
        }
    })

if __name__ == '__main__':
    # Первичная генерация при запуске
    print("Запуск YML генератора...")
    generate_yml()
    
    # Запуск автоматического обновления
    threading.Thread(target=auto_update, daemon=True).start()
    
    # Запуск Flask приложения
    app.run(host='0.0.0.0', port=8080, debug=False)
