import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional


def generate_uuid() -> str:
    """Генерирует уникальный идентификатор."""
    return str(uuid.uuid4())


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """
    Форматирует дату и время в строку.
    
    Args:
        dt: Дата и время для форматирования. Если None, используется текущее время.
    
    Returns:
        Отформатированная строка с датой и временем.
    """
    if dt is None:
        dt = datetime.now()
    
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def extract_entities(text: str) -> Dict[str, Any]:
    """
    Временная функция для извлечения сущностей из текста.
    В будущем будет заменена на более сложный анализ с помощью LLM.
    
    Args:
        text: Текст для анализа
    
    Returns:
        Словарь с извлеченными сущностями
    """
    entities = {
        "dates": [],
        "times": [],
        "persons": [],
        "locations": [],
        "tasks": []
    }
    
    # Очень простая реализация для примера
    if "завтра" in text.lower():
        entities["dates"].append("tomorrow")
    
    if "в 10" in text.lower() or "в 10:00" in text.lower():
        entities["times"].append("10:00")
    
    # В будущем здесь будет более сложная логика с использованием NLP
    
    return entities