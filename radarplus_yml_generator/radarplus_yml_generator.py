#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RadarPlus YML Generator
Скрипт для генерации YML файла выгрузки товаров из Directus API
для сайта RadarPlus (https://radarplus.shop) на Пульс Цен
"""

import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re
from datetime import datetime
import logging
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('radarplus_yml.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RadarPlusYMLGenerator:
    def __init__(self, api_base_url="http://radarplus.shop:8055", api_key=None):
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.session = requests.Session()
        
        # Устанавливаем заголовки авторизации если есть API ключ
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}'
            })
    
    def clean_html(self, text):
        """Очистка HTML тегов из текста"""
        if not text:
            return ""
        
        # Убираем HTML теги
        clean = re.compile('<.*?>')
        text = re.sub(clean, '', str(text))
        
        # Убираем лишние пробелы и переносы
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Экранируем XML специальные символы
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')
        
        return text
    
    def get_collections_data(self):
        """Получение данных из всех нужных коллекций"""
        try:
            # Получаем продукты
            products_response = self.session.get(f"{self.api_base_url}/items/products")
            products_response.raise_for_status()
            products = products_response.json().get('data', [])
            
            # Получаем категории
            categories_response = self.session.get(f"{self.api_base_url}/items/categories")
            categories_response.raise_for_status()
            categories = categories_response.json().get('data', [])
            
            # Получаем варианты продуктов
            variants_response = self.session.get(f"{self.api_base_url}/items/product_variants")
            variants_response.raise_for_status()
            variants = variants_response.json().get('data', [])
            
            logger.info(f"Получено: {len(products)} продуктов, {len(categories)} категорий, {len(variants)} вариантов")
            
            return {
                'products': products,
                'categories': categories,
                'variants': variants
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении данных из API: {e}")
            return None
    
    def create_categories_dict(self, categories):
        """Создание словаря категорий для быстрого доступа"""
        categories_dict = {}
        for category in categories:
            categories_dict[category.get('id')] = {
                'name': category.get('name', ''),
                'parent_id': category.get('parent_id')
            }
        return categories_dict
    
    def create_variants_dict(self, variants):
        """Создание словаря вариантов продуктов"""
        variants_dict = {}
        for variant in variants:
            product_id = variant.get('product_id')
            if product_id not in variants_dict:
                variants_dict[product_id] = []
            variants_dict[product_id].append(variant)
        return variants_dict
    
    def get_category_path(self, category_id, categories_dict):
        """Получение полного пути категории"""
        if not category_id or category_id not in categories_dict:
            return "Без категории"
        
        path = []
        current_id = category_id
        
        while current_id and current_id in categories_dict:
            category = categories_dict[current_id]
            path.insert(0, category['name'])
            current_id = category.get('parent_id')
        
        return "/".join(path) if path else "Без категории"
    
    def generate_yml(self, data, output_file="radarplus_export.yml"):
        """Генерация YML файла"""
        if not data:
            logger.error("Нет данных для генерации YML")
            return False
        
        try:
            # Создаем корневой элемент
            yml_catalog = ET.Element("yml_catalog", date=datetime.now().strftime("%Y-%m-%d %H:%M"))
            
            # Добавляем информацию о магазине
            shop = ET.SubElement(yml_catalog, "shop")
            
            # Основная информация о магазине
            ET.SubElement(shop, "name").text = "RadarPlus"
            ET.SubElement(shop, "company").text = "RadarPlus Shop"
            ET.SubElement(shop, "url").text = "https://radarplus.shop"
            
            # Валюты
            currencies = ET.SubElement(shop, "currencies")
            currency = ET.SubElement(currencies, "currency", id="UAH", rate="1")
            
            # Категории
            categories_element = ET.SubElement(shop, "categories")
            categories_dict = self.create_categories_dict(data['categories'])
            
            for category_id, category_info in categories_dict.items():
                category_attrs = {"id": str(category_id)}
                if category_info.get('parent_id'):
                    category_attrs["parentId"] = str(category_info['parent_id'])
                
                category_elem = ET.SubElement(categories_element, "category", category_attrs)
                category_elem.text = self.clean_html(category_info['name'])
            
            # Товары
            offers = ET.SubElement(shop, "offers")
            variants_dict = self.create_variants_dict(data['variants'])
            
            for product in data['products']:
                # Основной товар
                self.add_offer_to_xml(offers, product, categories_dict, variants_dict)
                
                # Варианты товара
                product_variants = variants_dict.get(product.get('id'), [])
                for variant in product_variants:
                    self.add_variant_offer_to_xml(offers, product, variant, categories_dict)
            
            # Сохраняем в файл
            self.save_pretty_xml(yml_catalog, output_file)
            logger.info(f"YML файл успешно создан: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при генерации YML: {e}")
            return False
    
    def add_offer_to_xml(self, offers_parent, product, categories_dict, variants_dict):
        """Добавление основного товара в XML"""
        product_id = product.get('id')
        if not product_id:
            return
        
        offer = ET.SubElement(offers_parent, "offer", id=str(product_id), available="true")
        
        # Основные поля
        ET.SubElement(offer, "name").text = self.clean_html(product.get('name', ''))
        ET.SubElement(offer, "url").text = f"https://radarplus.shop/product/{product_id}"
        
        # Цена
        price = product.get('price')
        if price:
            ET.SubElement(offer, "price").text = str(price)
        
        # Валюта
        ET.SubElement(offer, "currencyId").text = "UAH"
        
        # Категория
        category_id = product.get('category_id')
        if category_id:
            ET.SubElement(offer, "categoryId").text = str(category_id)
        
        # Изображения
        if product.get('image'):
            ET.SubElement(offer, "picture").text = f"https://radarplus.shop/assets/{product['image']}"
        
        # Описание
        description = product.get('description')
        if description:
            ET.SubElement(offer, "description").text = self.clean_html(description)
        
        # Характеристики
        specifications = product.get('specifications')
        if specifications:
            ET.SubElement(offer, "param", name="Характеристики").text = self.clean_html(specifications)
        
        # Артикул
        sku = product.get('sku')
        if sku:
            ET.SubElement(offer, "vendorCode").text = str(sku)
        
        # Статус товара
        status = product.get('status', 'published')
        if status != 'published':
            offer.set("available", "false")
    
    def add_variant_offer_to_xml(self, offers_parent, product, variant, categories_dict):
        """Добавление варианта товара в XML"""
        variant_id = variant.get('id')
        if not variant_id:
            return
        
        offer = ET.SubElement(offers_parent, "offer", id=f"{product.get('id')}-{variant_id}", available="true")
        
        # Название с вариантом
        product_name = self.clean_html(product.get('name', ''))
        variant_name = self.clean_html(variant.get('name', ''))
        full_name = f"{product_name} - {variant_name}" if variant_name else product_name
        
        ET.SubElement(offer, "name").text = full_name
        ET.SubElement(offer, "url").text = f"https://radarplus.shop/product/{product.get('id')}/variant/{variant_id}"
        
        # Цена варианта (если есть) или основного товара
        price = variant.get('price') or product.get('price')
        if price:
            ET.SubElement(offer, "price").text = str(price)
        
        # Валюта
        ET.SubElement(offer, "currencyId").text = "UAH"
        
        # Категория
        category_id = product.get('category_id')
        if category_id:
            ET.SubElement(offer, "categoryId").text = str(category_id)
        
        # Изображение варианта или основного товара
        image = variant.get('image') or product.get('image')
        if image:
            ET.SubElement(offer, "picture").text = f"https://radarplus.shop/assets/{image}"
        
        # Описание
        description = variant.get('description') or product.get('description')
        if description:
            ET.SubElement(offer, "description").text = self.clean_html(description)
        
        # Артикул варианта
        sku = variant.get('sku')
        if sku:
            ET.SubElement(offer, "vendorCode").text = str(sku)
        
        # Количество
        quantity = variant.get('stock_quantity')
        if quantity is not None:
            if quantity <= 0:
                offer.set("available", "false")
    
    def save_pretty_xml(self, root, filename):
        """Сохранение XML с красивым форматированием"""
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
        
        with open(filename, 'wb') as f:
            f.write(pretty_xml)
    
    def run(self, output_file="radarplus_export.yml"):
        """Основной метод запуска генерации"""
        logger.info("Начало генерации YML файла для RadarPlus")
        
        # Получаем данные
        data = self.get_collections_data()
        if not data:
            logger.error("Не удалось получить данные из API")
            return False
        
        # Генерируем YML
        success = self.generate_yml(data, output_file)
        
        if success:
            logger.info(f"Генерация завершена успешно. Файл: {output_file}")
        else:
            logger.error("Ошибка при генерации YML файла")
        
        return success

def main():
    """Главная функция"""
    # Можно передать API ключ через переменную окружения
    api_key = os.getenv('RADARPLUS_API_KEY')
    
    generator = RadarPlusYMLGenerator(api_key=api_key)
    
    # Генерируем YML файл
    output_file = f"radarplus_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yml"
    generator.run(output_file)

if __name__ == "__main__":
    main()
