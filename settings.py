"""
Настройки приложения
"""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""

    # АТОЛ Драйвер
    atol_driver_path: str = ""  # Абсолютный путь к libfptr10 (если не в системных путях)

    # Подключение к ККТ
    atol_connection_type: str = "tcp"  # tcp, usb, serial, bluetooth
    atol_host: str = "localhost"
    atol_port: int = 5555
    atol_serial_port: str = ""  # Для serial: COM3 или /dev/ttyS0
    atol_baudrate: int = 115200

    # Компания
    company_inn: str = ""
    company_payment_address: str = ""
    company_email: str = ""

    # Кассир по умолчанию
    cashier_name: str = "Кассир"
    cashier_inn: str = ""

    # API сервер
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False  # auto-reload для разработки

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Пути
    log_dir: Path = Path("logs")
    cache_dir: Path = Path("data/cache")
    receipts_dir: Path = Path("data/receipts")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Игнорировать дополнительные поля


settings = Settings()
