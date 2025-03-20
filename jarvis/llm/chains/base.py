from typing import Dict, List, Any, Optional
import logging

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from jarvis.llm.models import LLMService

logger = logging.getLogger(__name__)


class TaskExtractor(BaseModel):
    """Модель для извлечения задачи из текста."""
    
    task_type: str = Field(description="Тип задачи (напоминание, событие, покупка и т.д.)")
    task_description: str = Field(description="Описание задачи")
    deadline: Optional[str] = Field(description="Срок выполнения задачи (если указан)")
    assignees: Optional[List[str]] = Field(description="Назначенные лица (если указаны)")
    priority: Optional[str] = Field(description="Приоритет задачи (если указан)")


class IntentClassification(BaseModel):
    """Модель для классификации намерения пользователя."""
    
    intent: str = Field(description="Основное намерение пользователя")
    confidence: float = Field(description="Уверенность в классификации (0-1)")
    entities: Dict[str, Any] = Field(description="Извлеченные сущности")


class BaseLangChain:
    """Базовый класс для цепочек LangChain."""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Инициализация базовой цепочки.
        
        Args:
            llm_service: Сервис LLM для использования в цепочке
        """
        self.llm_service = llm_service or LLMService()
    
    async def process(self, *args, **kwargs):
        """
        Базовый метод для обработки запросов.
        Должен быть переопределен в подклассах.
        """
        raise NotImplementedError("Метод должен быть переопределен в подклассах")


class TaskExtractionChain(BaseLangChain):
    """Цепочка для извлечения задач из текста пользователя."""
    
    PROMPT_TEMPLATE = """
    Пожалуйста, проанализируй следующий текст пользователя и извлеки информацию о задаче.
    
    Текст пользователя: {user_text}
    
    Определи тип задачи, её описание, сроки выполнения, назначенных лиц и приоритет.
    
    {format_instructions}
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Инициализация цепочки извлечения задач."""
        super().__init__(llm_service)
        
        self.parser = PydanticOutputParser(pydantic_object=TaskExtractor)
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["user_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
    
    async def process(self, user_text: str) -> TaskExtractor:
        """
        Извлекает информацию о задаче из текста пользователя.
        
        Args:
            user_text: Текст пользователя"
        Returns:
            Извлеченная информация о задаче
        """
        try:
            # Форматируем промпт с текстом пользователя
            prompt_text = self.prompt.format(user_text=user_text)
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — аналитический ассистент, извлекающий структурированную информацию из текста."
            )
            
            # Парсим ответ в модель TaskExtractor
            return self.parser.parse(response)
        except Exception as e:
            logger.error(f"Ошибка при извлечении задачи: {str(e)}")
            # Возвращаем базовую задачу в случае ошибки
            return TaskExtractor(
                task_type="unknown",
                task_description=user_text,
                deadline=None,
                assignees=None,
                priority=None
            )


class IntentClassificationChain(BaseLangChain):
    """Цепочка для классификации намерения пользователя."""
    PROMPT_TEMPLATE = """
    Пожалуйста, проанализируй следующий текст пользователя и определи его намерение.

    Текст пользователя: {user_text}

    Возможные намерения:
    - task_creation: Создание новой задачи или напоминания
    - event_planning: Планирование события
    - shopping_list: Работа со списком покупок
    - budget_management: Управление бюджетом
    - meal_planning: Планирование питания
    - general_question: Общий вопрос
    - small_talk: Небольшой разговор

    Также извлеки любые релевантные сущности (даты, времена, люди, места и т.д.).

    {format_instructions}
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        """Инициализация цепочки классификации намерений."""
        super().__init__(llm_service)
        
        self.parser = PydanticOutputParser(pydantic_object=IntentClassification)
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["user_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

    async def process(self, user_text: str) -> IntentClassification:
        """
        Классифицирует намерение пользователя на основе текста.
        
        Args:
            user_text: Текст пользовательского запроса
        
        Returns:
            Классификация намерения
        """
        try:
            # Форматируем промпт с текстом пользователя
            prompt_text = self.prompt.format(user_text=user_text)
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — аналитический ассистент, классифицирующий намерения пользователя."
            )
            
            # Парсим ответ в модель IntentClassification
            return self.parser.parse(response)
        except Exception as e:
            logger.error(f"Ошибка при классификации намерения: {str(e)}")
            # Возвращаем базовую классификацию в случае ошибки
            return IntentClassification(
                intent="general_question",
                confidence=0.5,
                entities={}
            )
