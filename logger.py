"""
Настройка логирования
"""
import logging
from pathlib import Path


def setup_logger(name: str, log_file: str = None, level=logging.INFO):
    """Настроить логгер"""
    logger_instance = logging.getLogger(name)
    logger_instance.setLevel(level)

    # Предотвращаем дублирование хендлеров, если логгер уже был настроен
    if logger_instance.hasHandlers():
        logger_instance.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Консольный handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger_instance.addHandler(console_handler)

    # Файловый handler
    if log_file:
        log_path = Path("logs") / log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger_instance.addHandler(file_handler)

    return logger_instance

# Создаем и экспортируем логгер по умолчанию для всего приложения
logger = setup_logger("atol_integration", log_file="atol_integration.log")