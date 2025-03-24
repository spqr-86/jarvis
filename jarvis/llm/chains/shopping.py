"""
Цепочки LangChain для работы со списками покупок.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from jarvis.llm.models import LLMService
from jarvis.llm.chains.base import BaseLangChain
from jarvis.core.models.shopping import ItemCategory, ItemPriority

logger = logging.getLogger(__name__)


class ShoppingItemData(BaseModel):
    """Модель для извлечения информации о товаре из текста."""
    
    name: str = Field(description="Название товара")
    quantity: float = Field(1.0, description="Количество товара")
    unit: Optional[str] = Field(None, description="Единица измерения (кг, шт, л и т.д.)")
    category: ItemCategory = Field(ItemCategory.OTHER, description="Категория товара")
    priority: Optional[ItemPriority] = Field(None, description="Приоритет товара")
    notes: Optional[str] = Field(None, description="Дополнительные заметки")
    
    def dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь, исключая None-значения."""
        result = super().dict()
        
        # Если приоритет не указан, убираем его из словаря
        # чтобы использовалось значение по умолчанию
        if result.get("priority") is None:
            del result["priority"]
            
        return result


class MultipleShoppingItems(BaseModel):
    """Модель для извлечения нескольких товаров из текста."""
    
    items: List[ShoppingItemData] = Field(description="Список товаров")


class ShoppingIntent(BaseModel):
    """Модель для классификации намерения пользователя относительно списка покупок."""
    
    intent: str = Field(description="Намерение пользователя (add_item, view_list, mark_purchased, clear_list, etc.)")
    confidence: float = Field(description="Уверенность в классификации (0-1)")
    items: Optional[List[ShoppingItemData]] = Field(None, description="Извлеченные товары (если есть)")
    list_id: Optional[str] = Field(None, description="ID списка покупок (если указан)")
    list_name: Optional[str] = Field(None, description="Название списка покупок (если указано)")


class ShoppingItemExtractor(BaseLangChain):
    """Цепочка для извлечения информации о товарах из текста."""
    
    PROMPT_TEMPLATE = """
    Проанализируй следующий текст пользователя и извлеки информацию о товарах для списка покупок.
    
    Текст пользователя: {user_text}
    
    Определи название товара, количество, единицу измерения, категорию и, если указано, приоритет и заметки.
    Если в тексте упоминается несколько товаров, извлеки информацию о каждом из них.
    
    Категории товаров:
    - grocery: Бакалея (крупы, макароны, консервы, специи, масло, сахар и т.д.)
    - fruits: Фрукты
    - vegetables: Овощи
    - dairy: Молочные продукты (молоко, сыр, йогурт и т.д.)
    - meat: Мясо и рыба
    - bakery: Хлебобулочные изделия
    - frozen: Замороженные продукты
    - household: Товары для дома (бытовая химия, салфетки, туалетная бумага и т.д.)
    - personal_care: Средства личной гигиены (шампунь, мыло, зубная паста и т.д.)
    - other: Другое
    
    Приоритеты:
    - low: Низкий приоритет
    - medium: Средний приоритет (по умолчанию)
    - high: Высокий приоритет
    - urgent: Срочно нужно
    
    {format_instructions}
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Инициализация цепочки извлечения информации о товарах."""
        super().__init__(llm_service)
        
        self.parser = PydanticOutputParser(pydantic_object=MultipleShoppingItems)
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["user_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
    
    async def process(self, user_text: str) -> MultipleShoppingItems:
        """
        Извлекает информацию о товарах из текста пользователя.
        
        Args:
            user_text: Текст пользователя
            
        Returns:
            Извлеченная информация о товарах
        """
        try:
            # Форматируем промпт с текстом пользователя
            prompt_text = self.prompt.format(user_text=user_text)
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — аналитический ассистент, извлекающий информацию о товарах для списка покупок из текста."
            )
            
            # Парсим ответ в модель MultipleShoppingItems
            return self.parser.parse(response)
        except Exception as e:
            logger.error(f"Ошибка при извлечении информации о товарах: {str(e)}")
            # Возвращаем пустой список товаров в случае ошибки
            return MultipleShoppingItems(items=[])


class ShoppingIntentClassifier(BaseLangChain):
    """Цепочка для классификации намерения пользователя относительно списка покупок.
    
    Эта цепочка анализирует текст пользователя и определяет, какое действие
    со списком покупок пользователь хочет выполнить, а также извлекает
    связанные с этим действием данные (товары, идентификаторы списков и т.д.).
    """
    
    PROMPT_TEMPLATE = """
    Проанализируй следующий текст пользователя и определи его намерение относительно списка покупок.
    
    Текст пользователя: {user_text}
    
    Возможные намерения:
    - add_item: Добавить товар(ы) в список покупок
    - view_list: Просмотреть текущий список покупок
    - mark_purchased: Отметить товар(ы) как купленные
    - remove_item: Удалить товар(ы) из списка
    - clear_list: Очистить список покупок
    - create_list: Создать новый список покупок
    - change_priority: Изменить приоритет товара
    - other: Другое намерение, не связанное со списком покупок
    
    Также извлеки любые упомянутые товары и идентификаторы списков покупок, если они указаны.
    
    {format_instructions}
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Инициализация цепочки классификации намерений для списка покупок.
        
        Args:
            llm_service: Сервис LLM для использования в цепочке
        """
        super().__init__(llm_service)
        
        self.parser = PydanticOutputParser(pydantic_object=ShoppingIntent)
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["user_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
    
    async def process(self, user_text: str) -> ShoppingIntent:
        """
        Классифицирует намерение пользователя относительно списка покупок.
        
        Args:
            user_text: Текст пользователя
            
        Returns:
            Классификация намерения
        """
        try:
            # Форматируем промпт с текстом пользователя
            prompt_text = self.prompt.format(user_text=user_text)
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — аналитический ассистент, классифицирующий намерения пользователя относительно списка покупок."
            )
            
            # Парсим ответ в модель ShoppingIntent
            return self.parser.parse(response)
        except Exception as e:
            logger.error(f"Ошибка при классификации намерения относительно списка покупок: {str(e)}")
            # Возвращаем базовую классификацию в случае ошибки
            return ShoppingIntent(
                intent="other",
                confidence=0.5,
                items=None
            )


class ShoppingResponseGenerator(BaseLangChain):
    """Цепочка для генерации ответов на запросы пользователя относительно списка покупок."""
    
    PROMPT_TEMPLATE = """
    Пользователь взаимодействует со списком покупок. Сгенерируй естественный и полезный ответ.
    
    Намерение пользователя: {intent}
    Информация о товарах: {items_info}
    Информация о списке покупок: {list_info}
    Результат операции: {operation_result}
    
    Дай дружелюбный ответ, подтверждающий выполненное действие и предлагающий следующие шаги при необходимости.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Инициализация цепочки генерации ответов.
        
        Args:
            llm_service: Сервис LLM для использования в цепочке
        """
        super().__init__(llm_service)
        
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["intent", "items_info", "list_info", "operation_result"]
        )
    
    async def process(
        self,
        intent: str,
        items_info: str,
        list_info: str,
        operation_result: str
    ) -> str:
        """
        Генерирует ответ на запрос пользователя относительно списка покупок.
        
        Args:
            intent: Намерение пользователя
            items_info: Информация о товарах
            list_info: Информация о списке покупок
            operation_result: Результат операции
            
        Returns:
            Текст ответа
        """
        try:
            # Форматируем промпт с информацией
            prompt_text = self.prompt.format(
                intent=intent,
                items_info=items_info,
                list_info=list_info,
                operation_result=operation_result
            )
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — семейный ассистент, помогающий управлять списком покупок. Твои ответы должны быть дружелюбными, лаконичными и полезными."
            )
            
            return response
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа на запрос пользователя: {str(e)}")
            return "Извините, произошла ошибка при обработке запроса. Пожалуйста, попробуйте снова."


class ShoppingListManager:
    """Менеджер для работы со списками покупок, интегрирующий хранилище и LLM-цепочки."""
    
    def __init__(
        self,
        shopping_repository,
        llm_service: Optional[LLMService] = None
    ):
        """
        Инициализация менеджера списков покупок.
        
        Args:
            shopping_repository: Репозиторий для работы со списками покупок
            llm_service: Сервис LLM для использования в цепочках
        """
        self.repository = shopping_repository
        self.llm_service = llm_service or LLMService()
        
        # Инициализация цепочек
        self.item_extractor = ShoppingItemExtractor(self.llm_service)
        self.intent_classifier = ShoppingIntentClassifier(self.llm_service)
        self.response_generator = ShoppingResponseGenerator(self.llm_service)
    
    async def process_message(
        self,
        user_text: str,
        family_id: str,
        user_id: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Обрабатывает сообщение пользователя, связанное со списком покупок.
        
        Args:
            user_text: Текст пользователя
            family_id: ID семьи пользователя
            user_id: ID пользователя
            
        Returns:
            Кортеж (ответ пользователю, метаданные операции)
        """
        try:
            # Классифицируем намерение пользователя
            intent_result = await self.intent_classifier.process(user_text)
            
            # Если намерение не связано со списком покупок, возвращаем None
            if intent_result.intent == "other" or intent_result.confidence < 0.6:
                return None, {"intent": "other", "confidence": intent_result.confidence}
            
            # Получаем или создаем активный список покупок
            active_list = await self.repository.get_active_list_for_family(family_id)
            if not active_list and intent_result.intent != "create_list":
                # Если нет активного списка и пользователь не хочет создать новый, создаем его автоматически
                active_list = await self.repository.create_list(
                    name="Список покупок",
                    family_id=family_id,
                    created_by=user_id
                )
            
            # Обработка различных намерений
            operation_result = "успешно"
            items_info = "нет товаров"
            list_info = f"Список покупок: {active_list.name if active_list else 'не создан'}"
            
            if intent_result.intent == "create_list":
                # Создание нового списка
                list_name = intent_result.list_name or "Список покупок"
                active_list = await self.repository.create_list(
                    name=list_name,
                    family_id=family_id,
                    created_by=user_id
                )
                list_info = f"Создан новый список покупок: {active_list.name}"
                
            elif intent_result.intent == "add_item":
                # Добавление товаров в список
                if not intent_result.items:
                    # Если в намерении нет товаров, пытаемся извлечь их из текста
                    items_result = await self.item_extractor.process(user_text)
                    items = items_result.items
                else:
                    items = intent_result.items
                
                if not items:
                    operation_result = "не удалось определить товары для добавления"
                else:
                    added_items = []
                    for item in items:
                        success, added_item = await self.repository.add_item(
                            list_id=active_list.id,
                            name=item.name,
                            quantity=item.quantity,
                            unit=item.unit,
                            category=item.category,
                            priority=item.priority or ItemPriority.MEDIUM,
                            notes=item.notes
                        )
                        if success:
                            added_items.append(added_item)
                    
                    items_info = f"Добавлено товаров: {len(added_items)}"
                    if added_items:
                        items_info += f" ({', '.join([item.name for item in added_items])})"
            
            elif intent_result.intent == "view_list":
                # Просмотр списка
                if not active_list:
                    list_info = "У вас нет активного списка покупок"
                else:
                    unpurchased = active_list.get_unpurchased_items()
                    purchased = active_list.get_purchased_items()
                    
                    list_info = f"Список покупок '{active_list.name}':\n"
                    list_info += f"- Товаров к покупке: {len(unpurchased)}\n"
                    list_info += f"- Уже куплено: {len(purchased)}\n"
                    
                    if unpurchased:
                        items_info = "Товары к покупке: " + ", ".join([f"{item.name} ({item.quantity}{' ' + item.unit if item.unit else ''})" for item in unpurchased[:5]])
                        if len(unpurchased) > 5:
                            items_info += f" и еще {len(unpurchased) - 5}"
            
            elif intent_result.intent == "mark_purchased":
                # Отметка товаров как купленных
                if not active_list:
                    operation_result = "нет активного списка покупок"
                elif not intent_result.items:
                    operation_result = "не указаны товары для отметки"
                else:
                    marked_items = []
                    for item_data in intent_result.items:
                        # Находим товар по имени (упрощенный поиск)
                        for list_item in active_list.get_unpurchased_items():
                            if item_data.name.lower() in list_item.name.lower():
                                success = await self.repository.mark_item_as_purchased(
                                    list_id=active_list.id,
                                    item_id=list_item.id,
                                    by_user_id=user_id
                                )
                                if success:
                                    marked_items.append(list_item)
                    
                    if marked_items:
                        items_info = f"Отмечено как купленное: {', '.join([item.name for item in marked_items])}"
                    else:
                        operation_result = "не найдены указанные товары в списке"
            
            elif intent_result.intent == "remove_item":
                # Удаление товаров из списка
                if not active_list:
                    operation_result = "нет активного списка покупок"
                elif not intent_result.items:
                    operation_result = "не указаны товары для удаления"
                else:
                    removed_items = []
                    for item_data in intent_result.items:
                        # Находим товар по имени (упрощенный поиск)
                        for list_item in active_list.items:
                            if item_data.name.lower() in list_item.name.lower():
                                success = await self.repository.remove_item(
                                    list_id=active_list.id,
                                    item_id=list_item.id
                                )
                                if success:
                                    removed_items.append(list_item.name)
                    
                    if removed_items:
                        items_info = f"Удалено из списка: {', '.join(removed_items)}"
                    else:
                        operation_result = "не найдены указанные товары в списке"
            
            elif intent_result.intent == "clear_list":
                # Очистка списка
                if not active_list:
                    operation_result = "нет активного списка покупок"
                else:
                    # Удаляем все товары
                    for item in active_list.items[:]:  # Копируем список, чтобы избежать проблем при итерации
                        await self.repository.remove_item(active_list.id, item.id)
                    
                    list_info = f"Список покупок '{active_list.name}' очищен"
            
            elif intent_result.intent == "change_priority":
                # Изменение приоритета товара
                if not active_list:
                    operation_result = "нет активного списка покупок"
                elif not intent_result.items:
                    operation_result = "не указаны товары для изменения приоритета"
                else:
                    updated_items = []
                    for item_data in intent_result.items:
                        if not item_data.priority:
                            continue
                            
                        # Находим товар по имени (упрощенный поиск)
                        for list_item in active_list.items:
                            if item_data.name.lower() in list_item.name.lower():
                                success = await self.repository.update_item(
                                    list_id=active_list.id,
                                    item_id=list_item.id,
                                    priority=item_data.priority
                                )
                                if success:
                                    updated_items.append((list_item.name, item_data.priority))
                    
                    if updated_items:
                        items_info = "Обновлены приоритеты: " + ", ".join([f"{name} ({ItemPriority.get_ru_name(priority)})" for name, priority in updated_items])
                    else:
                        operation_result = "не найдены указанные товары в списке"
            
            # Генерируем ответ на основе результатов операции
            response = await self.response_generator.process(
                intent=intent_result.intent,
                items_info=items_info,
                list_info=list_info,
                operation_result=operation_result
            )
            
            return response, {
                "intent": intent_result.intent,
                "confidence": intent_result.confidence,
                "list_id": active_list.id if active_list else None,
                "operation_result": operation_result == "успешно"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения пользователя: {str(e)}")
            return "Извините, произошла ошибка при обработке запроса. Пожалуйста, попробуйте снова.", {
                "error": str(e)
            }