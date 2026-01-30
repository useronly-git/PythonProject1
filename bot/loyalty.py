import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from bot.database import Database
from config.settings import settings

logger = logging.getLogger(__name__)


class LoyaltySystem:
    def __init__(self, db: Database):
        self.db = db

    async def get_user_points(self, telegram_id: int) -> int:
        """Получение баланса баллов пользователя"""
        async with self.db.connect() as db:
            cursor = await db.execute('''
                                      SELECT COALESCE(SUM(points), 0) as total_points
                                      FROM loyalty_points lp
                                               JOIN users u ON lp.user_id = u.id
                                      WHERE u.telegram_id = ?
                                      ''', (telegram_id,))

            row = await cursor.fetchone()
            return row[0] if row else 0

    async def add_points(self, telegram_id: int, points: int, reason: str, order_id: Optional[int] = None):
        """Добавление баллов пользователю"""
        async with self.db.connect() as db:
            # Получаем ID пользователя
            cursor = await db.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            user_row = await cursor.fetchone()

            if not user_row:
                logger.error(f"Пользователь {telegram_id} не найден")
                return

            user_id = user_row[0]

            # Добавляем баллы
            await db.execute('''
                             INSERT INTO loyalty_points (user_id, points, reason, order_id, created_at)
                             VALUES (?, ?, ?, ?, ?)
                             ''', (user_id, points, reason, order_id, datetime.now()))

            await db.commit()

            logger.info(f"Добавлено {points} баллов пользователю {telegram_id} за {reason}")

    async def get_user_level(self, telegram_id: int) -> Dict:
        """Получение уровня пользователя"""
        points = await self.get_user_points(telegram_id)

        async with self.db.connect() as db:
            cursor = await db.execute('''
                                      SELECT name, discount, color
                                      FROM loyalty_levels
                                      WHERE min_points <= ?
                                      ORDER BY min_points DESC LIMIT 1
                                      ''', (points,))

            current_level = await cursor.fetchone()

            cursor = await db.execute('''
                                      SELECT name, min_points
                                      FROM loyalty_levels
                                      WHERE min_points > ?
                                      ORDER BY min_points ASC LIMIT 1
                                      ''', (points,))

            next_level = await cursor.fetchone()

            level_info = {
                'name': current_level[0] if current_level else 'Новичок',
                'discount': current_level[1] if current_level else 0,
                'color': current_level[2] if current_level else '#95a5a6',
                'points': points,
                'next_level': next_level[0] if next_level else None,
                'points_needed': next_level[1] - points if next_level else 0
            }

            return level_info

    async def get_points_history(self, telegram_id: int, limit: int = 10) -> List[Dict]:
        """Получение истории начисления баллов"""
        async with self.db.connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT lp.points, lp.reason, lp.created_at, o.id as order_id
                                      FROM loyalty_points lp
                                               JOIN users u ON lp.user_id = u.id
                                               LEFT JOIN orders o ON lp.order_id = o.id
                                      WHERE u.telegram_id = ?
                                      ORDER BY lp.created_at DESC LIMIT ?
                                      ''', (telegram_id, limit))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def sync_with_external(self, telegram_id: int):
        """Синхронизация с внешней системой лояльности"""
        if not settings.SYNC_ENABLED or not settings.EXTERNAL_LOYALTY_API:
            return None

        try:
            import aiohttp
            import json

            user_data = await self.db.get_user_data(telegram_id)
            if not user_data:
                return None

            async with aiohttp.ClientSession() as session:
                # Получаем текущие баллы из внешней системы
                async with session.get(
                        f"{settings.EXTERNAL_LOYALTY_API}/points/{telegram_id}"
                ) as response:
                    if response.status == 200:
                        external_data = await response.json()
                        external_points = external_data.get('points', 0)

                        # Синхронизируем если есть расхождения
                        current_points = await self.get_user_points(telegram_id)

                        if external_points != current_points:
                            # Обновляем в нашей системе
                            diff = external_points - current_points
                            if diff != 0:
                                await self.add_points(
                                    telegram_id,
                                    diff,
                                    "Синхронизация с внешней системой"
                                )

                            return {
                                'synced': True,
                                'points_added': diff,
                                'new_total': external_points
                            }

            return {'synced': True, 'points_added': 0}

        except Exception as e:
            logger.error(f"Ошибка синхронизации с внешней системой: {e}")
            return None

    async def exchange_points(self, telegram_id: int, points: int, target: str = 'discount') -> Dict:
        """Обмен баллов на скидку или бонусы"""
        current_points = await self.get_user_points(telegram_id)

        if points > current_points:
            return {
                'success': False,
                'message': 'Недостаточно баллов'
            }

        if target == 'discount':
            # Рассчитываем скидку в рублях
            discount_rubles = points / settings.POINTS_PER_RUBLE

            # Добавляем запись о списании баллов
            await self.add_points(
                telegram_id,
                -points,
                f"Обмен на скидку {discount_rubles}₽"
            )

            return {
                'success': True,
                'message': f'Получена скидка {discount_rubles}₽',
                'discount': discount_rubles,
                'points_spent': points
            }

        elif target == 'product':
            # Здесь можно реализовать обмен на конкретные товары
            # Получаем доступные товары для обмена
            available_products = await self.get_available_products_for_points(points)

            return {
                'success': True,
                'available_products': available_products,
                'points_spent': points
            }

        return {
            'success': False,
            'message': 'Неизвестная цель обмена'
        }

    async def get_available_products_for_points(self, points: int) -> List[Dict]:
        """Получение товаров доступных для обмена на баллы"""
        async with self.db.connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT id, name, price, image_url
                                      FROM menu_items
                                      WHERE available = 1
                                        AND price <= ? * ?
                                      ORDER BY price DESC LIMIT 10
                                      ''', (points, settings.RUBLES_PER_POINT))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_loyalty_stats(self) -> Dict:
        """Статистика программы лояльности"""
        async with self.db.connect() as db:
            # Общее количество баллов
            cursor = await db.execute('''
                                      SELECT COALESCE(SUM(points), 0)                              as total_points,
                                             COUNT(DISTINCT user_id)                               as active_users,
                                             SUM(CASE WHEN points > 0 THEN points ELSE 0 END)      as points_earned,
                                             SUM(CASE WHEN points < 0 THEN ABS(points) ELSE 0 END) as points_spent
                                      FROM loyalty_points
                                      ''')

            stats = dict(await cursor.fetchone())

            # Распределение по уровням
            cursor = await db.execute('''
                                      SELECT ll.name,
                                             COUNT(DISTINCT u.id) as users_count
                                      FROM users u
                                               LEFT JOIN loyalty_levels ll ON (SELECT COALESCE(SUM(points), 0)
                                                                               FROM loyalty_points lp
                                                                               WHERE lp.user_id = u.id) >= ll.min_points
                                      GROUP BY ll.name
                                      ORDER BY ll.min_points
                                      ''')

            levels_stats = []
            for row in await cursor.fetchall():
                levels_stats.append({
                    'level': row[0],
                    'users': row[1]
                })

            stats['levels'] = levels_stats

            return stats