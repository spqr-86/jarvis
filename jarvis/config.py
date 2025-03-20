import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

# Базовые настройки
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# LLM API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

# Vector Database
CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma")

# По умолчанию используем Groq для разработки
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "groq")

# Проверка обязательных переменных
def validate_config() -> Dict[str, Optional[str]]:
    """Проверяет наличие обязательных переменных конфигурации."""
    missing_vars = {}
    
    if not TELEGRAM_BOT_TOKEN:
        missing_vars["TELEGRAM_BOT_TOKEN"] = None
    
    if DEFAULT_LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        missing_vars["OPENAI_API_KEY"] = None
    elif DEFAULT_LLM_PROVIDER == "groq" and not GROQ_API_KEY:
        missing_vars["GROQ_API_KEY"] = None
    elif DEFAULT_LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        missing_vars["ANTHROPIC_API_KEY"] = None
    elif DEFAULT_LLM_PROVIDER == "huggingface" and not HUGGINGFACE_API_KEY:
        missing_vars["HUGGINGFACE_API_KEY"] = None
    
    return missing_vars