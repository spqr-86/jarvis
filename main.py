"""
Точка входа для запуска Jarvis - семейного ассистента на базе Telegram.
"""

import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jarvis.config import validate_config
from jarvis.bot.bot import run_bot
from jarvis.storage.database import engine, Base

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("jarvis.log")
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Главная функция для запуска приложения."""
    # Проверяем конфигурацию
    missing_vars = validate_config()
    if missing_vars:
        error_msg = "Отсутствуют обязательные переменные окружения:\n"
        for var in missing_vars:
            error_msg += f"- {var}\n"
        logger.error(error_msg)
        sys.exit(1)
    
    Base.metadata.create_all(bind=engine)
    
    # Создаем директории, необходимые для работы приложения
    Path("./data/chroma").mkdir(parents=True, exist_ok=True)
    
    logger.info("Запуск Jarvis - семейного ассистента на базе Telegram...")
    
    try:
        # Запускаем Telegram бота
        run_bot()
    except KeyboardInterrupt:
        logger.info("Завершение работы по запросу пользователя...")
    except Exception as e:
        logger.error(f"Произошла ошибка при запуске приложения: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()