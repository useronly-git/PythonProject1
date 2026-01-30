import sqlite3
import aiosqlite
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.db_path = settings.DATABASE_PATH
        self.init_database()

    def init_database(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Пользователи
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS users
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               telegram_id
                               INTEGER
                               UNIQUE
                               NOT
                               NULL,
                               username
                               TEXT,
                               first_name
                               TEXT
                               NOT
                               NULL,
                               last_name
                               TEXT,
                               phone
                               TEXT,
                               email
                               TEXT,
                               balance
                               REAL
                               DEFAULT
                               0,
                               total_orders
                               INTEGER
                               DEFAULT
                               0,
                               total_spent
                               REAL
                               DEFAULT
                               0,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               last_active
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           ''')

            # Программа лояльности
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS loyalty_points
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               user_id
                               INTEGER
                               NOT
                               NULL,
                               points
                               INTEGER
                               NOT
                               NULL,
                               reason
                               TEXT,
                               order_id
                               INTEGER,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               FOREIGN
                               KEY
                           (
                               user_id
                           ) REFERENCES users
                           (
                               id
                           )
                               )
                           ''')

            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS loyalty_levels
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               name
                               TEXT
                               NOT
                               NULL,
                               min_points
                               INTEGER
                               NOT
                               NULL,
                               discount
                               INTEGER
                               NOT
                               NULL,
                               color
                               TEXT
                               DEFAULT
                               '#3498db'
                           )
                           ''')

            # Категории меню
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS categories
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               name
                               TEXT
                               NOT
                               NULL
                               UNIQUE,
                               emoji
                               TEXT,
                               position
                               INTEGER
                               DEFAULT
                               0
                           )
                           ''')

            # Меню
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS menu_items
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               category_id
                               INTEGER,
                               name
                               TEXT
                               NOT
                               NULL,
                               description
                               TEXT,
                               price
                               REAL
                               NOT
                               NULL,
                               image_url
                               TEXT,
                               available
                               BOOLEAN
                               DEFAULT
                               1,
                               position
                               INTEGER
                               DEFAULT
                               0,
                               external_id
                               TEXT
                               UNIQUE,
                               sync_enabled
                               BOOLEAN
                               DEFAULT
                               0,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               updated_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               FOREIGN
                               KEY
                           (
                               category_id
                           ) REFERENCES categories
                           (
                               id
                           )
                               )
                           ''')

            # Заказы
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS orders
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               user_id
                               INTEGER
                               NOT
                               NULL,
                               total_amount
                               REAL
                               NOT
                               NULL,
                               status
                               TEXT
                               DEFAULT
                               'pending',
                               payment_method
                               TEXT
                               DEFAULT
                               'cash',
                               delivery_type
                               TEXT
                               DEFAULT
                               'pickup',
                               address
                               TEXT,
                               phone
                               TEXT,
                               notes
                               TEXT,
                               scheduled_time
                               TIMESTAMP,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               updated_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               external_sync
                               BOOLEAN
                               DEFAULT
                               0,
                               FOREIGN
                               KEY
                           (
                               user_id
                           ) REFERENCES users
                           (
                               id
                           )
                               )
                           ''')

            # Позиции заказа
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS order_items
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               order_id
                               INTEGER
                               NOT
                               NULL,
                               menu_item_id
                               INTEGER
                               NOT
                               NULL,
                               quantity
                               INTEGER
                               NOT
                               NULL,
                               price
                               REAL
                               NOT
                               NULL,
                               notes
                               TEXT,
                               FOREIGN
                               KEY
                           (
                               order_id
                           ) REFERENCES orders
                           (
                               id
                           ),
                               FOREIGN KEY
                           (
                               menu_item_id
                           ) REFERENCES menu_items
                           (
                               id
                           )
                               )
                           ''')

            # Настройки
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS settings
                           (
                               key
                               TEXT
                               PRIMARY
                               KEY,
                               value
                               TEXT,
                               updated_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           ''')

            # Внешние интеграции
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS external_sync
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               entity_type
                               TEXT
                               NOT
                               NULL,
                               entity_id
                               INTEGER
                               NOT
                               NULL,
                               external_id
                               TEXT,
                               sync_status
                               TEXT
                               DEFAULT
                               'pending',
                               last_sync
                               TIMESTAMP,
                               UNIQUE
                           (
                               entity_type,
                               entity_id
                           )
                               )
                           ''')

            # Добавляем начальные данные
            self._add_initial_data(cursor)

            conn.commit()

    def _add_initial_data(self, cursor):
        """Добавление начальных данных"""
        # Категории
        categories = [
            ('coffee', '☕', 1),
            ('tea', '🍵', 2),
            ('bakery', '🥐', 3),
            ('dessert', '🍰', 4),
            ('food', '🥪', 5)
        ]

        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT INTO categories (name, emoji, position) VALUES (?, ?, ?)",
                categories
            )

        # Уровни лояльности
        levels = [
            ('Новичок', 0, 0, '#95a5a6'),
            ('Любитель', 100, 5, '#3498db'),
            ('Постоянный', 500, 10, '#9b59b6'),
            ('VIP', 1000, 15, '#e74c3c'),
            ('Легенда', 5000, 20, '#f1c40f')
        ]

        cursor.execute("SELECT COUNT(*) FROM loyalty_levels")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT INTO loyalty_levels (name, min_points, discount, color) VALUES (?, ?, ?, ?)",
                levels
            )

        # Пример меню
        cursor.execute("SELECT COUNT(*) FROM menu_items")
        if cursor.fetchone()[0] == 0:
            self._add_sample_menu(cursor)

    def _add_sample_menu(self, cursor):
        """Добавление примерного меню"""
        # Получаем ID категорий
        cursor.execute("SELECT id, name FROM categories")
        categories = {name: id for id, name in cursor.fetchall()}

        sample_items = [
            (categories['coffee'], 'Капучино', 'Классический капучино с молоком', 180,
             'https://via.placeholder.com/300x200/4a2c2a/ffffff?text=Cappuccino', 1, 1),
            (categories['coffee'], 'Латте', 'Нежный латте с молочной пенкой', 190,
             'https://via.placeholder.com/300x200/4a2c2a/ffffff?text=Latte', 1, 2),
            (categories['coffee'], 'Американо', 'Крепкий американо', 150,
             'https://via.placeholder.com/300x200/4a2c2a/ffffff?text=Americano', 1, 3),
            (categories['coffee'], 'Эспрессо', 'Двойной эспрессо', 120,
             'https://via.placeholder.com/300x200/4a2c2a/ffffff?text=Espresso', 1, 4),
            (categories['coffee'], 'Раф ванильный', 'Ванильный раф с карамелью', 220,
             'https://via.placeholder.com/300x200/4a2c2a/ffffff?text=Raf', 1, 5),
            (categories['tea'], 'Чай черный', 'Ассам с бергамотом', 150,
             'https://via.placeholder.com/300x200/27ae60/ffffff?text=Black+Tea', 1, 1),
            (categories['tea'], 'Чай зеленый', 'Жасминовый зеленый чай', 160,
             'https://via.placeholder.com/300x200/27ae60/ffffff?text=Green+Tea', 1, 2),
            (categories['bakery'], 'Круассан', 'Свежий круассан с шоколадом', 120,
             'https://via.placeholder.com/300x200/e67e22/ffffff?text=Croissant', 1, 1),
            (categories['bakery'], 'Маффин', 'Шоколадный маффин', 130,
             'https://via.placeholder.com/300x200/e67e22/ffffff?text=Muffin', 1, 2),
            (categories['dessert'], 'Чизкейк', 'Нью-йоркский чизкейк', 250,
             'https://via.placeholder.com/300x200/9b59b6/ffffff?text=Cheesecake', 1, 1),
            (categories['dessert'], 'Тирамису', 'Классический тирамису', 280,
             'https://via.placeholder.com/300x200/9b59b6/ffffff?text=Tiramisu', 1, 2),
            (categories['food'], 'Сэндвич', 'С курицей и овощами', 200,
             'https://via.placeholder.com/300x200/e74c3c/ffffff?text=Sandwich', 1, 1),
            (categories['food'], 'Салат Цезарь', 'С курицей и соусом', 300,
             'https://via.placeholder.com/300x200/e74c3c/ffffff?text=Caesar', 1, 2),
        ]

        cursor.executemany(
            """INSERT INTO menu_items
                   (category_id, name, description, price, image_url, available, position)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            sample_items
        )

    async def register_user(self, user):
        """Регистрация пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT
                OR IGNORE INTO users 
                (telegram_id, username, first_name, last_name, created_at) 
                VALUES (?, ?, ?, ?, ?)""",
                (user.id, user.username, user.first_name, user.last_name, datetime.now())
            )

            await db.execute(
                """UPDATE users
                   SET last_active = ?,
                       username    = COALESCE(?, username),
                       first_name  = COALESCE(?, first_name),
                       last_name   = COALESCE(?, last_name)
                   WHERE telegram_id = ?""",
                (datetime.now(), user.username, user.first_name, user.last_name, user.id)
            )

            await db.commit()

    async def get_user_data(self, telegram_id: int) -> Dict:
        """Получение данных пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT *,
                          (SELECT COUNT(*) FROM orders WHERE user_id = users.id)                       as total_orders,
                          (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE user_id = users.id) as total_spent,
                          (SELECT COALESCE(AVG(total_amount), 0) FROM orders WHERE user_id = users.id) as avg_order
                   FROM users
                   WHERE telegram_id = ?""",
                (telegram_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_menu_categories(self) -> List[str]:
        """Получение категорий меню"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM categories ORDER BY position"
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def get_menu_items_by_category(self, category: str) -> List[Dict]:
        """Получение товаров по категории"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT mi.*
                                      FROM menu_items mi
                                               JOIN categories c ON mi.category_id = c.id
                                      WHERE c.name = ?
                                        AND mi.available = 1
                                      ORDER BY mi.position
                                      ''', (category,))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_menu_items(self) -> List[Dict]:
        """Получение всех товаров меню"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT mi.*, c.name as category_name, c.emoji as category_emoji
                                      FROM menu_items mi
                                               JOIN categories c ON mi.category_id = c.id
                                      WHERE mi.available = 1
                                      ORDER BY c.position, mi.position
                                      ''')

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def create_order(self, user_id: int, order_data: Dict) -> int:
        """Создание заказа"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем ID пользователя в базе
            cursor = await db.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (user_id,)
            )
            user_row = await cursor.fetchone()
            if not user_row:
                raise ValueError("Пользователь не найден")

            db_user_id = user_row[0]

            # Создаем заказ
            cursor = await db.execute('''
                                      INSERT INTO orders
                                      (user_id, total_amount, status, payment_method, delivery_type,
                                       address, phone, notes, scheduled_time, created_at)
                                      VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)
                                      ''', (
                                          db_user_id,
                                          order_data['total'],
                                          order_data.get('paymentMethod', 'cash'),
                                          order_data.get('deliveryType', 'pickup'),
                                          order_data.get('address'),
                                          order_data.get('phone'),
                                          order_data.get('notes'),
                                          order_data.get('scheduledTime'),
                                          datetime.now()
                                      ))

            order_id = cursor.lastrowid

            # Добавляем позиции заказа
            for item in order_data['items']:
                await db.execute('''
                                 INSERT INTO order_items
                                     (order_id, menu_item_id, quantity, price, notes)
                                 VALUES (?, ?, ?, ?, ?)
                                 ''', (
                                     order_id,
                                     item['id'],
                                     item['quantity'],
                                     item['price'],
                                     item.get('notes')
                                 ))

            # Обновляем статистику пользователя
            await db.execute('''
                             UPDATE users
                             SET total_orders = total_orders + 1,
                                 total_spent  = total_spent + ?,
                                 last_active  = ?
                             WHERE id = ?
                             ''', (order_data['total'], datetime.now(), db_user_id))

            await db.commit()
            return order_id

    async def get_user_orders(self, telegram_id: int, limit: int = 10) -> List[Dict]:
        """Получение заказов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT o.*
                                      FROM orders o
                                               JOIN users u ON o.user_id = u.id
                                      WHERE u.telegram_id = ?
                                      ORDER BY o.created_at DESC LIMIT ?
                                      ''', (telegram_id, limit))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_order(self, order_id: int) -> Optional[Dict]:
        """Получение информации о заказе"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT o.*, u.telegram_id, u.first_name, u.username
                                      FROM orders o
                                               JOIN users u ON o.user_id = u.id
                                      WHERE o.id = ?
                                      ''', (order_id,))

            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_order_status(self, order_id: int, status: str):
        """Обновление статуса заказа"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                             UPDATE orders
                             SET status     = ?,
                                 updated_at = ?
                             WHERE id = ?
                             ''', (status, datetime.now(), order_id))
            await db.commit()

    async def get_admin_stats(self) -> Dict:
        """Получение статистики для админа"""
        async with aiosqlite.connect(self.db_path) as db:
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)

            # Заказы за сегодня
            cursor = await db.execute('''
                                      SELECT COUNT(*)                                                          as total_orders,
                                             SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END)               as new_orders,
                                             SUM(CASE
                                                     WHEN status IN ('confirmed', 'preparing', 'on_delivery') THEN 1
                                                     ELSE 0 END)                                               as processing_orders,
                                             SUM(CASE WHEN status IN ('delivered', 'ready') THEN 1 ELSE 0 END) as completed_orders,
                                             COALESCE(SUM(total_amount), 0)                                    as revenue,
                                             COALESCE(AVG(total_amount), 0)                                    as avg_order
                                      FROM orders
                                      WHERE DATE (created_at) = DATE (?)
                                      ''', (datetime.now(),))

            stats = dict(await cursor.fetchone())

            # Новые пользователи сегодня
            cursor = await db.execute('''
                                      SELECT COUNT(*) as new_users
                                      FROM users
                                      WHERE DATE (created_at) = DATE (?)
                                      ''', (datetime.now(),))

            stats.update(dict(await cursor.fetchone()))

            # Активные пользователи (за последние 7 дней)
            cursor = await db.execute('''
                                      SELECT COUNT(DISTINCT user_id) as active_users
                                      FROM orders
                                      WHERE created_at >= DATETIME(?, '-7 days')
                                      ''', (datetime.now(),))

            stats.update(dict(await cursor.fetchone()))

            return stats

    async def sync_menu_from_external(self, menu_data: List[Dict]):
        """Синхронизация меню с внешним источником"""
        async with aiosqlite.connect(self.db_path) as db:
            for item in menu_data:
                # Проверяем существует ли уже товар с таким external_id
                if item.get('external_id'):
                    cursor = await db.execute(
                        "SELECT id FROM menu_items WHERE external_id = ?",
                        (item['external_id'],)
                    )
                    existing = await cursor.fetchone()

                    if existing:
                        # Обновляем существующий
                        await db.execute('''
                                         UPDATE menu_items
                                         SET name        = ?,
                                             description = ?,
                                             price       = ?,
                                             available   = ?,
                                             updated_at  = ?
                                         WHERE external_id = ?
                                         ''', (
                                             item['name'],
                                             item.get('description', ''),
                                             item['price'],
                                             item.get('available', 1),
                                             datetime.now(),
                                             item['external_id']
                                         ))
                    else:
                        # Добавляем новый
                        category_id = await self.get_or_create_category(db, item.get('category', 'other'))

                        await db.execute('''
                                         INSERT INTO menu_items
                                         (category_id, name, description, price, available, external_id, sync_enabled)
                                         VALUES (?, ?, ?, ?, ?, ?, 1)
                                         ''', (
                                             category_id,
                                             item['name'],
                                             item.get('description', ''),
                                             item['price'],
                                             item.get('available', 1),
                                             item['external_id']
                                         ))

            await db.commit()

    async def get_or_create_category(self, db, category_name: str) -> int:
        """Получить или создать категорию"""
        cursor = await db.execute(
            "SELECT id FROM categories WHERE name = ?",
            (category_name,)
        )
        row = await cursor.fetchone()

        if row:
            return row[0]
        else:
            cursor = await db.execute(
                "INSERT INTO categories (name, position) VALUES (?, (SELECT COALESCE(MAX(position), 0) + 1 FROM categories))",
                (category_name,)
            )
            return cursor.lastrowid

    async def export_menu_to_json(self) -> List[Dict]:
        """Экспорт меню в JSON формат"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT mi.id,
                                             mi.name,
                                             mi.description,
                                             mi.price,
                                             mi.available,
                                             c.name as category,
                                             mi.external_id,
                                             mi.sync_enabled
                                      FROM menu_items mi
                                               LEFT JOIN categories c ON mi.category_id = c.id
                                      ''')

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]