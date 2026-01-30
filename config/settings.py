import os
import json
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # Бот
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list = json.loads(os.getenv("ADMIN_IDS", "[]"))
    ORDER_CHAT_ID: str = os.getenv("ORDER_CHAT_ID", "")

    # Web App
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "http://localhost:8080")
    ADMIN_PANEL_URL: str = os.getenv("ADMIN_PANEL_URL", f"{WEBAPP_URL}/admin")

    # Внешние интеграции (можно отключить)
    EXTERNAL_MENU_API: Optional[str] = os.getenv("EXTERNAL_MENU_API")
    EXTERNAL_LOYALTY_API: Optional[str] = os.getenv("EXTERNAL_LOYALTY_API")
    SYNC_ENABLED: bool = os.getenv("SYNC_ENABLED", "false").lower() == "true"

    # Программа лояльности
    LOYALTY_ENABLED: bool = os.getenv("LOYALTY_ENABLED", "true").lower() == "true"
    POINTS_PER_RUBLE: float = float(os.getenv("POINTS_PER_RUBLE", "1"))
    RUBLES_PER_POINT: float = float(os.getenv("RUBLES_PER_POINT", "100"))

    # Кофейня
    SHOP_NAME: str = os.getenv("SHOP_NAME", "Coffee Bliss")
    SHOP_ADDRESS: str = os.getenv("SHOP_ADDRESS", "ул. Кофейная, 15")
    SHOP_PHONE: str = os.getenv("SHOP_PHONE", "+7 (999) 123-45-67")
    DELIVERY_FEE: int = int(os.getenv("DELIVERY_FEE", "150"))
    MIN_ORDER: int = int(os.getenv("MIN_ORDER", "300"))

    # Время работы
    OPENING_TIME: str = os.getenv("OPENING_TIME", "08:00")
    CLOSING_TIME: str = os.getenv("CLOSING_TIME", "22:00")

    # База данных
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "coffee_shop.db")

    def validate(self):
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен")
        return self


settings = Settings().validate()