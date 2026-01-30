import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

from config.settings import settings
from bot.database import Database
from bot.admin import AdminPanel
from bot.loyalty import LoyaltySystem

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
CHOOSING, TYPING_REPLY, TYPING_CHOICE = range(3)


class CoffeeShopBot:
    def __init__(self):
        self.db = Database()
        self.admin = AdminPanel(self.db)
        self.loyalty = LoyaltySystem(self.db)
        self.application = Application.builder().token(settings.BOT_TOKEN).build()

        # Загрузка меню из внешнего API если включено
        if settings.SYNC_ENABLED and settings.EXTERNAL_MENU_API:
            asyncio.create_task(self.sync_external_menu())

        self.setup_handlers()

    async def sync_external_menu(self):
        """Синхронизация меню с внешним API"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(settings.EXTERNAL_MENU_API) as response:
                    if response.status == 200:
                        menu_data = await response.json()
                        await self.db.sync_menu_from_external(menu_data)
                        logger.info("Меню синхронизировано с внешним API")
        except Exception as e:
            logger.error(f"Ошибка синхронизации меню: {e}")

    def setup_handlers(self):
        """Настройка всех обработчиков"""

        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("menu", self.show_menu))
        self.application.add_handler(CommandHandler("orders", self.show_my_orders))
        self.application.add_handler(CommandHandler("profile", self.show_profile))
        self.application.add_handler(CommandHandler("balance", self.show_balance))

        # Админ команды
        self.application.add_handler(CommandHandler("admin", self.admin_panel))

        # Callback запросы
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

        # Web App данные
        self.application.add_handler(MessageHandler(
            filters.StatusUpdate.WEB_APP_DATA,
            self.process_webapp_data
        ))

        # Текстовые сообщения
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))

        # Настройка кнопки меню
        asyncio.run(self.setup_menu_button())

    async def setup_menu_button(self):
        """Настройка кнопки меню в боте"""
        await self.application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🛒 Заказать",
                web_app=WebAppInfo(url=settings.WEBAPP_URL)
            )
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        await self.db.register_user(user)

        # Приветственное сообщение с красивым интерфейсом
        welcome_text = f"""
🎉 *Добро пожаловать в {settings.SHOP_NAME}!* ☕

*Мы рады видеть вас, {user.first_name}!*

✨ *Наши преимущества:*
• 🚀 Быстрое приготовление
• 🌱 Свежие ингредиенты
• 💫 Авторские рецепты
• 🎁 Программа лояльности

📱 *Используйте кнопку "🛒 Заказать" или команды ниже:*
"""

        keyboard = [
            [
                InlineKeyboardButton("📋 Посмотреть меню", callback_data="view_menu"),
                InlineKeyboardButton("🛒 Открыть Mini App", web_app=WebAppInfo(url=settings.WEBAPP_URL))
            ],
            [
                InlineKeyboardButton("👤 Мой профиль", callback_data="profile"),
                InlineKeyboardButton("💎 Баланс баллов", callback_data="balance")
            ],
            [
                InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders"),
                InlineKeyboardButton("⭐ Избранное", callback_data="favorites")
            ],
            [
                InlineKeyboardButton("🏆 Акции", callback_data="promotions"),
                InlineKeyboardButton("📍 Контакты", callback_data="contacts")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message:
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать категории меню"""
        categories = await self.db.get_menu_categories()

        text = "☕ *Наше меню*\n\nВыберите категорию:"

        keyboard = []
        for category in categories:
            emoji = {
                'coffee': '☕',
                'tea': '🍵',
                'bakery': '🥐',
                'dessert': '🍰',
                'food': '🥪'
            }.get(category, '📋')

            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {category.capitalize()}",
                    callback_data=f"category_{category}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🛒 Открыть полное меню в Mini App",
                web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}")
            )
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    async def show_my_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать историю заказов"""
        user_id = update.effective_user.id
        orders = await self.db.get_user_orders(user_id)

        if not orders:
            text = "📭 *У вас еще нет заказов*\n\nСделайте свой первый заказ через Mini App! 🛒"
            keyboard = [[InlineKeyboardButton(
                "🛒 Сделать заказ",
                web_app=WebAppInfo(url=settings.WEBAPP_URL)
            )]]
        else:
            text = "📦 *Ваши последние заказы:*\n\n"
            for order in orders[:3]:
                status_info = self.get_order_status_info(order['status'])
                text += f"{status_info['emoji']} *Заказ #{order['id']}*\n"
                text += f"📅 {order['created_at']}\n"
                text += f"💰 {order['total_amount']}₽\n"
                text += f"📊 {status_info['text']}\n"
                text += "─" * 20 + "\n"

            text += "\n*Полную историю смотрите в Mini App*"

            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_orders")],
                [InlineKeyboardButton("📊 Подробнее в Mini App", web_app=WebAppInfo(
                    url=f"{settings.WEBAPP_URL}/orders.html"
                ))]
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    async def show_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать профиль пользователя"""
        user = update.effective_user
        user_data = await self.db.get_user_data(user.id)

        if settings.LOYALTY_ENABLED:
            points = await self.loyalty.get_user_points(user.id)
            level = await self.loyalty.get_user_level(user.id)
        else:
            points = 0
            level = {"name": "Новичок", "discount": 0}

        text = f"""
👤 *Ваш профиль*

*Имя:* {user.first_name}
*Ник:* @{user.username if user.username else 'не указан'}
*ID:* `{user.id}`

"""
        if settings.LOYALTY_ENABLED:
            text += f"""
🎯 *Программа лояльности*
🏅 Уровень: *{level['name']}*
💎 Баллы: *{points}*
🎁 Скидка: *{level['discount']}%*

📊 *Статистика:*
📦 Всего заказов: {user_data.get('total_orders', 0)}
💰 Общая сумма: {user_data.get('total_spent', 0)}₽
⭐ Средний чек: {user_data.get('avg_order', 0)}₽
"""

        keyboard = [
            [InlineKeyboardButton("✏️ Изменить данные", callback_data="edit_profile")],
            [InlineKeyboardButton("💳 Пополнить баланс", callback_data="add_balance")],
            [InlineKeyboardButton("🎁 Мои бонусы", callback_data="my_bonuses")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    async def show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать баланс баллов"""
        if not settings.LOYALTY_ENABLED:
            await update.message.reply_text(
                "❌ Программа лояльности временно недоступна",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        user_id = update.effective_user.id
        points = await self.loyalty.get_user_points(user_id)
        level = await self.loyalty.get_user_level(user_id)
        history = await self.loyalty.get_points_history(user_id, limit=5)

        text = f"""
💎 *Ваш баланс*

*Текущий уровень:* {level['name']}
*Ваши баллы:* *{points}*
*Скидка:* {level['discount']}%

📊 *Курс баллов:*
• 1 балл = {settings.RUBLES_PER_POINT}₽
• 100₽ = {settings.POINTS_PER_RUBLE * 100} баллов

📈 *Последние операции:*
"""

        for record in history:
            emoji = "➕" if record['points'] > 0 else "➖"
            text += f"{emoji} {record['points']} баллов - {record['reason']}\n"

        text += f"\n💡 *Следующий уровень:* {level.get('next_level', 'Максимальный')}"

        keyboard = [
            [InlineKeyboardButton("🔄 Обменять баллы", callback_data="exchange_points")],
            [InlineKeyboardButton("📊 Полная история", callback_data="points_history")],
            [InlineKeyboardButton("🎯 Условия программы", callback_data="loyalty_terms")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Панель администратора"""
        user_id = update.effective_user.id

        if str(user_id) not in settings.ADMIN_IDS:
            await update.message.reply_text("⛔ У вас нет доступа к админ-панели")
            return

        text = """
⚡ *Панель администратора*

Выберите действие:
"""

        keyboard = [
            [
                InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton("📦 Заказы", callback_data="admin_orders")
            ],
            [
                InlineKeyboardButton("📋 Меню", callback_data="admin_menu"),
                InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton("💰 Финансы", callback_data="admin_finance"),
                InlineKeyboardButton("🎁 Акции", callback_data="admin_promos")
            ],
            [
                InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings"),
                InlineKeyboardButton("📱 Открыть админку", web_app=WebAppInfo(
                    url=settings.ADMIN_PANEL_URL
                ))
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback запросов"""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "view_menu":
            await self.show_menu_callback(query)
        elif data == "profile":
            await self.show_profile_callback(query)
        elif data == "balance":
            await self.show_balance_callback(query)
        elif data == "my_orders":
            await self.show_my_orders_callback(query)
        elif data.startswith("category_"):
            category = data.split("_")[1]
            await self.show_category_items(query, category)
        elif data == "refresh_orders":
            await self.refresh_orders(query)
        elif data.startswith("admin_"):
            await self.handle_admin_callback(query, data)

    async def show_menu_callback(self, query):
        """Показать меню в callback"""
        categories = await self.db.get_menu_categories()

        text = "☕ *Наше меню*\n\nВыберите категорию:"

        keyboard = []
        for category in categories:
            emoji = {
                'coffee': '☕',
                'tea': '🍵',
                'bakery': '🥐',
                'dessert': '🍰',
                'food': '🥪'
            }.get(category, '📋')

            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {category.capitalize()}",
                    callback_data=f"category_{category}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🛒 Открыть полное меню",
                web_app=WebAppInfo(url=settings.WEBAPP_URL)
            )
        ])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

    async def show_category_items(self, query, category):
        """Показать товары категории"""
        items = await self.db.get_menu_items_by_category(category)

        emoji = {
            'coffee': '☕',
            'tea': '🍵',
            'bakery': '🥐',
            'dessert': '🍰',
            'food': '🥪'
        }.get(category, '📋')

        text = f"{emoji} *{category.capitalize()}*\n\n"

        for item in items[:5]:  # Показываем первые 5 товаров
            text += f"• *{item['name']}* - {item['price']}₽\n"

        if len(items) > 5:
            text += f"\n...и еще {len(items) - 5} позиций"

        keyboard = [
            [InlineKeyboardButton("🛒 Открыть в Mini App", web_app=WebAppInfo(
                url=f"{settings.WEBAPP_URL}/?category={category}"
            ))],
            [InlineKeyboardButton("⬅️ Назад", callback_data="view_menu")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

    async def process_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка данных из Web App"""
        try:
            data = json.loads(update.message.web_app_data.data)
            user = update.effective_user
            action = data.get('action')

            if action == 'create_order':
                await self.process_order(user, data)
            elif action == 'update_profile':
                await self.update_user_profile(user, data)
            elif action == 'exchange_points':
                await self.process_points_exchange(user, data)

        except Exception as e:
            logger.error(f"Ошибка обработки Web App данных: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
                parse_mode=ParseMode.MARKDOWN
            )

    async def process_order(self, user, data):
        """Обработка нового заказа"""
        try:
            # Создаем заказ в базе
            order_id = await self.db.create_order(user.id, data)

            # Начисляем баллы если включена программа лояльности
            if settings.LOYALTY_ENABLED:
                points = int(data['total'] * settings.POINTS_PER_RUBLE)
                await self.loyalty.add_points(
                    user.id,
                    points,
                    f"Заказ #{order_id}"
                )

            # Отправляем подтверждение пользователю
            order_text = self.format_order_confirmation(order_id, data)
            await self.application.bot.send_message(
                chat_id=user.id,
                text=order_text,
                parse_mode=ParseMode.MARKDOWN
            )

            # Отправляем уведомление администратору/чату
            await self.notify_admins(order_id, data, user)

            # Синхронизируем с внешней системой если нужно
            if settings.SYNC_ENABLED and settings.EXTERNAL_LOYALTY_API:
                await self.sync_order_external(order_id, data, user.id)

        except Exception as e:
            logger.error(f"Ошибка обработки заказа: {e}")
            raise

    async def notify_admins(self, order_id: int, order_data: dict, user):
        """Уведомление администраторов о новом заказе"""
        notification = self.format_admin_notification(order_id, order_data, user)

        # Отправляем в чат заказов если указан
        if settings.ORDER_CHAT_ID:
            try:
                await self.application.bot.send_message(
                    chat_id=settings.ORDER_CHAT_ID,
                    text=notification,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Ошибка отправки в чат: {e}")

        # Отправляем личным сообщениям администраторам
        for admin_id in settings.ADMIN_IDS:
            try:
                await self.application.bot.send_message(
                    chat_id=int(admin_id),
                    text=notification,
                    parse_mode=ParseMode.MARKDOWN
                )

                # Добавляем кнопки для быстрого управления заказом
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Принять", callback_data=f"accept_{order_id}"),
                        InlineKeyboardButton("⏳ В процессе", callback_data=f"process_{order_id}")
                    ],
                    [
                        InlineKeyboardButton("🚚 Готово", callback_data=f"ready_{order_id}"),
                        InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order_id}")
                    ],
                    [
                        InlineKeyboardButton("📞 Позвонить", url=f"tel:{order_data.get('phone', '')}"),
                        InlineKeyboardButton("💬 Написать",
                                             url=f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}")
                    ]
                ]

                await self.application.bot.send_message(
                    chat_id=int(admin_id),
                    text="⚡ *Быстрые действия:*",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )

            except Exception as e:
                logger.error(f"Ошибка отправки админу {admin_id}: {e}")

    def format_order_confirmation(self, order_id: int, order_data: dict) -> str:
        """Форматирование подтверждения заказа"""
        delivery_type = "🚶‍♂️ Самовывоз" if order_data.get('deliveryType') == 'pickup' else "🚗 Доставка"
        scheduled_text = f"⏰ *На время:* {order_data.get('scheduledTime')}\n" if order_data.get('scheduledTime') else ""

        text = f"""
🎉 *Заказ #{order_id} принят!*

{delivery_type}
{scheduled_text}
💰 *Сумма:* {order_data['total']}₽

📋 *Состав заказа:*
"""

        for item in order_data['items']:
            text += f"• {item['name']} × {item['quantity']} = {item['price'] * item['quantity']}₽\n"

        if order_data.get('notes'):
            text += f"\n📝 *Примечание:* {order_data['notes']}\n"

        text += f"""

⏳ *Статус:* Обрабатывается
📱 *Отслеживать статус:* /orders

💡 *Наш адрес:* {settings.SHOP_ADDRESS}
📞 *Телефон:* {settings.SHOP_PHONE}
"""

        return text

    def format_admin_notification(self, order_id: int, order_data: dict, user) -> str:
        """Форматирование уведомления для администратора"""
        delivery_type = "Самовывоз" if order_data.get('deliveryType') == 'pickup' else "Доставка"
        scheduled_text = f"*На время:* {order_data.get('scheduledTime')}\n" if order_data.get('scheduledTime') else ""

        text = f"""
🚨 *НОВЫЙ ЗАКАЗ #{order_id}*

👤 *Клиент:* {user.first_name} (@{user.username if user.username else 'без username'})
📞 *Телефон:* {order_data.get('phone', 'не указан')}
📦 *Тип:* {delivery_type}
{scheduled_text}💰 *Сумма:* {order_data['total']}₽

📍 *Адрес:* {order_data.get('address', settings.SHOP_ADDRESS) if delivery_type == 'Доставка' else settings.SHOP_ADDRESS}

📋 *Заказ:*
"""

        for item in order_data['items']:
            text += f"• {item['name']} × {item['quantity']}\n"

        if order_data.get('notes'):
            text += f"\n💬 *Примечание:* {order_data['notes']}\n"

        text += f"\n🆔 *ID заказа:* `{order_id}`"
        text += f"\n👤 *ID клиента:* `{user.id}`"

        return text

    def get_order_status_info(self, status: str) -> dict:
        """Информация о статусе заказа"""
        statuses = {
            'pending': {'emoji': '⏳', 'text': 'Ожидает подтверждения'},
            'confirmed': {'emoji': '✅', 'text': 'Подтвержден'},
            'preparing': {'emoji': '👨‍🍳', 'text': 'Готовится'},
            'ready': {'emoji': '🚀', 'text': 'Готов к выдаче'},
            'on_delivery': {'emoji': '🚗', 'text': 'В пути'},
            'delivered': {'emoji': '🎉', 'text': 'Доставлен'},
            'cancelled': {'emoji': '❌', 'text': 'Отменен'}
        }
        return statuses.get(status, {'emoji': '📝', 'text': status})

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        text = update.message.text

        if text.lower() in ['привет', 'hello', 'start', 'начать']:
            await self.start(update, context)
        else:
            await update.message.reply_text(
                "👋 Используйте команды или кнопки для навигации!\n\n"
                "Основные команды:\n"
                "/start - Главное меню\n"
                "/menu - Посмотреть меню\n"
                "/orders - Мои заказы\n"
                "/profile - Мой профиль\n"
                "/balance - Баланс баллов\n\n"
                "Или нажмите кнопку 🛒 в меню бота для оформления заказа!",
                parse_mode=ParseMode.MARKDOWN
            )

    async def handle_admin_callback(self, query, data):
        """Обработка админ callback"""
        user_id = query.from_user.id

        if str(user_id) not in settings.ADMIN_IDS:
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        if data == "admin_stats":
            await self.show_admin_stats(query)
        elif data == "admin_orders":
            await self.show_admin_orders(query)
        elif data.startswith("accept_"):
            order_id = int(data.split("_")[1])
            await self.accept_order(query, order_id)
        elif data.startswith("process_"):
            order_id = int(data.split("_")[1])
            await self.process_order_admin(query, order_id)
        elif data.startswith("ready_"):
            order_id = int(data.split("_")[1])
            await self.ready_order(query, order_id)
        elif data.startswith("cancel_"):
            order_id = int(data.split("_")[1])
            await self.cancel_order(query, order_id)

    async def show_admin_stats(self, query):
        """Показать статистику для админа"""
        stats = await self.db.get_admin_stats()

        text = f"""
📊 *Статистика за сегодня*

📦 *Заказы:*
• Всего: {stats['total_orders']}
• Новые: {stats['new_orders']}
• В процессе: {stats['processing_orders']}
• Завершенные: {stats['completed_orders']}

💰 *Финансы:*
• Выручка: {stats['revenue']}₽
• Средний чек: {stats['avg_order']}₽

👥 *Пользователи:*
• Новые: {stats['new_users']}
• Активные: {stats['active_users']}

⏰ *Время:* {datetime.now().strftime('%H:%M')}
"""

        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton("📈 Подробная статистика", web_app=WebAppInfo(
                url=f"{settings.ADMIN_PANEL_URL}/stats"
            ))]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

    async def accept_order(self, query, order_id):
        """Принять заказ"""
        await self.db.update_order_status(order_id, 'confirmed')
        await query.answer(f"Заказ #{order_id} принят!", show_alert=True)

        # Уведомляем пользователя
        order = await self.db.get_order(order_id)
        if order:
            await self.application.bot.send_message(
                chat_id=order['user_id'],
                text=f"✅ *Ваш заказ #{order_id} принят и готовится!*"
            )

        await self.show_admin_orders(query)

    async def run(self):
        """Запуск бота"""
        logger.info("🚀 Бот запускается...")
        logger.info(f"👥 Админы: {settings.ADMIN_IDS}")
        logger.info(f"🏪 Магазин: {settings.SHOP_NAME}")

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        logger.info("✅ Бот успешно запущен!")

        # Бесконечный цикл
        await asyncio.Event().wait()


def main():
    """Точка входа"""
    bot = CoffeeShopBot()

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")


if __name__ == "__main__":
    main()