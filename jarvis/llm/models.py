from typing import Dict, List, Optional, Any, Union
import logging

from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEndpoint
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.schema.messages import BaseMessage

from jarvis.config import (
    OPENAI_API_KEY, 
    GROQ_API_KEY, 
    ANTHROPIC_API_KEY,
    HUGGINGFACE_API_KEY,
    DEFAULT_LLM_PROVIDER
)

logger = logging.getLogger(__name__)


class LLMService:
    """Сервис для работы с LLM моделями."""
    
    def __init__(self, provider: Optional[str] = None):
        """
        Инициализация сервиса LLM.
        
        Args:
            provider: Провайдер LLM ("openai", "groq", "anthropic", "huggingface")
                      Если None, используется DEFAULT_LLM_PROVIDER из конфигурации
        """
        self.provider = provider or DEFAULT_LLM_PROVIDER
        self.model = self._initialize_model()
    
    def _initialize_model(self):
        """Инициализирует модель LLM на основе выбранного провайдера."""
        if self.provider == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY не указан в конфигурации")
            
            return ChatOpenAI(
                api_key=OPENAI_API_KEY,
                model="gpt-4o",  # Можно настроить через конфигурацию
                temperature=0.7,
            )
        
        elif self.provider == "groq":
            if not GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY не указан в конфигурации")
            
            return ChatGroq(
                api_key=GROQ_API_KEY,
                model="llama3-70b-8192",  # Или другая модель Groq
                temperature=0.7,
            )
                
        elif self.provider == "huggingface":
            if not HUGGINGFACE_API_KEY:
                raise ValueError("HUGGINGFACE_API_KEY не указан в конфигурации")
            
            return HuggingFaceEndpoint(
                endpoint_url="https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
                huggingfacehub_api_token=HUGGINGFACE_API_KEY,
                temperature=0.7,
            )
        
        else:
            raise ValueError(f"Неизвестный провайдер LLM: {self.provider}")
    
    async def generate_response(
        self, 
        prompt: str, 
        system_message: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Генерирует ответ от LLM.
        
        Args:
            prompt: Запрос пользователя
            system_message: Системное сообщение для LLM
            chat_history: История чата в формате [{role: content}, ...]
                          где role может быть "user" или "assistant"
        
        Returns:
            Ответ от LLM
        """
        messages: List[BaseMessage] = []
        
        # Добавляем системное сообщение, если оно предоставлено
        if system_message:
            messages.append(SystemMessage(content=system_message))
        
        # Добавляем историю чата, если она предоставлена
        if chat_history:
            for message in chat_history:
                if message["role"] == "user":
                    messages.append(HumanMessage(content=message["content"]))
                elif message["role"] == "assistant":
                    messages.append(AIMessage(content=message["content"]))
        
        # Добавляем текущий запрос пользователя
        messages.append(HumanMessage(content=prompt))
        
        try:
            # Генерируем ответ
            response = await self.model.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа от LLM: {str(e)}")
            return "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте снова."