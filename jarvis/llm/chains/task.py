from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from jarvis.llm.models import LLMService
from jarvis.llm.chains.base import BaseLangChain, TaskExtractor

logger = logging.getLogger(__name__)


class TaskResponse(BaseModel):
    """Модель для ответа на запрос о задаче."""
    
    success: bool = Field(description="Успешно ли создана/обновлена задача")
    message: str = Field(description="Сообщение для пользователя")
    task_id: Optional[str] = Field(description="ID задачи (если создана)")
    details: Optional[Dict[str, Any]] = Field(description="Дополнительные детали")


class TaskCreationChain(BaseLangChain):
    """Цепочка для создания новых задач."""
    
    PROMPT_TEMPLATE = """
    Пользователь хочет создать новую задачу. Помоги сформулировать детали задачи и подтверди её создание.
    
    Информация о задаче:
    - Тип: {task_type}
    - Описание: {task_description}
    - Срок: {deadline}
    - Назначена: {assignees}
    - Приоритет: {priority}
    
    Пожалуйста, подтверди создание задачи и предложи дополнительные детали, если необходимо.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Инициализация цепочки создания задач."""
        super().__init__(llm_service)
        
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["task_type", "task_description", "deadline", "assignees", "priority"]
        )
    
    async def process(self, task: TaskExtractor) -> TaskResponse:
        """
        Создает новую задачу на основе извлеченной информации.
        
        Args:
            task: Извлеченная информация о задаче
        
        Returns:
            Ответ с результатом создания задачи
        """
        try:
            # Подготавливаем значения для промпта
            task_dict = task.dict()
            # Преобразуем None значения в строки "Не указано"
            for key, value in task_dict.items():
                if value is None:
                    task_dict[key] = "Не указано"
                elif isinstance(value, list) and not value:
                    task_dict[key] = "Не указано"
            
            # Форматируем промпт
            prompt_text = self.prompt.format(**task_dict)
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — помощник, создающий и управляющий задачами семьи. Твоя цель — помочь пользователю создать понятную и полезную задачу."
            )
            
            # В реальном приложении здесь был бы код для сохранения задачи в базу данных
            # Но для MVP мы просто возвращаем успешный ответ
            task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            return TaskResponse(
                success=True,
                message=response,
                task_id=task_id,
                details={
                    "created_at": datetime.now().isoformat(),
                    "task_info": task.dict()
                }
            )
        except Exception as e:
            logger.error(f"Ошибка при создании задачи: {str(e)}")
            return TaskResponse(
                success=False,
                message="Произошла ошибка при создании задачи. Пожалуйста, попробуйте снова."
            )