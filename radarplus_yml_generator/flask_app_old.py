#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask веб-приложение для RadarPlus YML Generator
Предоставляет веб-интерфейс для генерации и получения YML файлов
"""

from flask import Flask, Response, jsonify, render_template_string, request
from radarplus_yml_generator import RadarPlusYMLGenerator
import os
import threading
import time
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные для кэширования
last_generated = None
yml_content = None
generation_lock = threading.Lock()

# HTML шаблон для главной страницы
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RadarPlus YML Generator</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        .info {
            background-color: #e9f4ff;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            border-left: 4px solid #007bff;
        }
        .button {
            display: inline-block;
            background-color: #007bff;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px 5px;
            border: none;
            cursor: pointer;
            font-size: 16px;
        }
        .button:hover {
            background-color: #0056b3;
        }
        .success {
            color: #28a745;
            font-weight: bold;
        }
        .error {
            color: #dc3545;
            font-weight: bold;
        }
        .status {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            border: 1px solid #dee2e6;
        }
        pre {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            border: 1px solid #dee2e6;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 RadarPlus YML Generator</h1>
        
        <div class="info">
            <h3>📋 Информация о сервисе</h3>
            <p><strong>Цель:</strong> Автоматическая генерация YML файла для выгрузки товаров с сайта RadarPlus на Пульс Цен</p>
            <p><strong>Источник данных:</strong> Directus API (http://radarplus.shop:8055)</p>
            <p><strong>Обновление:</strong> По запросу или автоматически</p>
        </div>

        <div class="status">
            <h3>📊 Статус системы</h3>
            <p><strong>Последняя генерация:</strong> 
                {% if last_generated %}
                    <span class="success">{{ last_generated }}</span>
                {% else %}
                    <span class="error">Файл еще не генерировался</span>
                {% endif %}
            </p>
            <p><strong>Статус YML файла:</strong> 
                {% if yml_available %}
                    <span class="success">✅ Доступен</span>
                {% else %}
                    <span class="error">❌ Не доступен</span>
                {% endif %}
            </p>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="/yml" class="button">📥 Скачать YML файл</a>
            <a href="/generate" class="button">🔄 Сгенерировать заново</a>
            <a href="/status" class="button">📊 Статус API</a>
        </div>

        <div class="info">
            <h3>🔗 Полезные ссылки</h3>
            <ul>
                <li><a href="/yml" target="_blank">Прямая ссылка на YML файл</a></li>
                <li><a href="/api/status" target="_blank">API статус (JSON)</a></li>
                <li><a href="https://radarplus.shop" target="_blank">Сайт RadarPlus</a></li>
                <li><a href="https://pulszen.ru" target="_blank">Пульс Цен</a></li>
            </ul>
        </div>

        <div class="info">
            <h3>⚙️ Инструкции по использованию</h3>
            <ol>
                <li><strong>Для Пульс Цен:</strong> Используйте ссылку <code>{{ request.url_root }}yml</code> в настройках выгрузки</li>
                <li><strong>Автоматическое обновление:</strong> Файл обновляется каждые 6 часов</li>
                <li><strong>Ручное обновление:</strong> Используйте кнопку "Сгенерировать заново"</li>
                <li><strong>Мониторинг:</strong> Проверяйте статус через API или веб-интерфейс</li>
            </ol>
        </div>
    </div>
</body>
</html>
"""

def generate_yml_file():
    """Генерация YML файла в фоновом режиме"""
    global last_generated, yml_content
    
    with generation_lock:
        try:
            logger.info("Начинаем генерацию YML файла...")
            
            # Получаем API ключ из переменной окружения
            api_key = os.getenv('RADARPLUS_API_KEY')
            
            generator = RadarPlusYMLGenerator(api_key=api_key)
            
            # Временный файл для генерации
            temp_file = f"temp_export_{int(time.time())}.yml"
            
            if generator.run(temp_file):
                # Читаем сгенерированный файл
                with open(temp_file, 'rb') as f:
                    yml_content = f.read()
                
                # Удаляем временный файл
                os.remove(temp_file)
                
                last_generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"YML файл успешно сгенерирован в {last_generated}")
                return True
            else:
                logger.error("Ошибка при генерации YML файла")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка в generate_yml_file: {e}")
            return False

@app.route('/')
def index():
    """Главная страница"""
    return render_template_string(HTML_TEMPLATE, 
                                last_generated=last_generated,
                                yml_available=yml_content is not None,
                                request=request)

@app.route('/yml')
def get_yml():
    """Отдача YML файла"""
    global yml_content, last_generated
    
    # Если файл не был сгенерирован или старше 6 часов, генерируем новый
    if yml_content is None or (last_generated and 
        (datetime.now() - datetime.strptime(last_generated, "%Y-%m-%d %H:%M:%S")).seconds > 21600):
        
        logger.info("YML файл устарел или отсутствует, генерируем новый...")
        
        # Запускаем генерацию в отдельном потоке, если она не выполняется
        if not generation_lock.locked():
            thread = threading.Thread(target=generate_yml_file)
            thread.start()
            thread.join(timeout=30)  # Ждем максимум 30 секунд
    
    if yml_content is None:
        return jsonify({
            'error': 'YML файл не доступен',
            'message': 'Попробуйте сгенерировать файл через /generate'
        }), 503
    
    return Response(
        yml_content,
        mimetype='application/xml',
        headers={
            'Content-Disposition': 'attachment; filename=radarplus_export.yml',
            'Content-Type': 'application/xml; charset=utf-8'
        }
    )

@app.route('/generate')
def generate():
    """Принудительная генерация YML файла"""
    if generation_lock.locked():
        return jsonify({
            'status': 'warning',
            'message': 'Генерация уже выполняется, подождите...'
        })
    
    # Запускаем генерацию в отдельном потоке
    thread = threading.Thread(target=generate_yml_file)
    thread.start()
    thread.join(timeout=30)  # Ждем максимум 30 секунд
    
    if yml_content is not None:
        return jsonify({
            'status': 'success',
            'message': 'YML файл успешно сгенерирован',
            'last_generated': last_generated,
            'download_url': '/yml'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Ошибка при генерации YML файла'
        }), 500

@app.route('/status')
def status():
    """Страница статуса"""
    try:
        # Проверяем доступность API
        generator = RadarPlusYMLGenerator()
        test_response = generator.session.get(f"{generator.api_base_url}/collections", timeout=5)
        api_status = "✅ Доступен" if test_response.status_code == 200 else "❌ Недоступен"
    except:
        api_status = "❌ Недоступен"
    
    status_html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Статус RadarPlus YML Generator</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .status {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .success {{ color: #28a745; }}
            .error {{ color: #dc3545; }}
        </style>
    </head>
    <body>
        <h1>📊 Статус системы</h1>
        <div class="status">
            <h3>API Directus</h3>
            <p><strong>Статус:</strong> {api_status}</p>
            <p><strong>URL:</strong> http://radarplus.shop:8055</p>
        </div>
        <div class="status">
            <h3>YML Генератор</h3>
            <p><strong>Последняя генерация:</strong> {last_generated or 'Не выполнялась'}</p>
            <p><strong>Статус файла:</strong> {'✅ Доступен' if yml_content else '❌ Не доступен'}</p>
        </div>
        <p><a href="/">← Назад на главную</a></p>
    </body>
    </html>
    """
    
    return status_html

@app.route('/api/status')
def api_status():
    """API статус в JSON формате"""
    try:
        # Проверяем доступность API Directus
        generator = RadarPlusYMLGenerator()
        test_response = generator.session.get(f"{generator.api_base_url}/collections", timeout=5)
        api_available = test_response.status_code == 200
    except:
        api_available = False
    
    return jsonify({
        'api_status': 'online' if api_available else 'offline',
        'api_url': 'http://radarplus.shop:8055',
        'yml_generator_status': 'online',
        'last_generated': last_generated,
        'yml_available': yml_content is not None,
        'timestamp': datetime.now().isoformat()
    })

def background_scheduler():
    """Фоновая задача для автоматической генерации"""
    while True:
        try:
            # Генерируем каждые 6 часов (21600 секунд)
            time.sleep(21600)
            logger.info("Запуск автоматической генерации YML файла...")
            generate_yml_file()
        except Exception as e:
            logger.error(f"Ошибка в фоновом планировщике: {e}")
            time.sleep(300)  # Повторяем через 5 минут при ошибке

if __name__ == '__main__':
    # Генерируем первый файл при запуске
    logger.info("Генерируем первоначальный YML файл...")
    generate_yml_file()
    
    # Запускаем фоновый планировщик
    scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Запускаем Flask приложение
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
