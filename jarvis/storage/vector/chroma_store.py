import os
from typing import List, Dict, Any, Optional, Union
import logging

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from jarvis.config import CHROMA_PERSIST_DIRECTORY, HUGGINGFACE_API_KEY

logger = logging.getLogger(__name__)


def clean_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Очищает метаданные от значений None, заменяя их на пустые строки.
    ChromaDB требует, чтобы все значения были str, int, float или bool.
    
    Args:
        metadata: Исходные метаданные
        
    Returns:
        Очищенные метаданные
    """
    # Логируем входные данные
    logger.info(f"Очистка метаданных: {metadata}")
    
    if metadata is None:
        logger.warning("Метаданные равны None, возвращаем пустой словарь")
        return {}
    
    if not isinstance(metadata, dict):
        logger.error(f"Метаданные не являются словарем: {type(metadata)}, {metadata}")
        return {}
        
    cleaned = {}
    for key, value in metadata.items():
        logger.info(f"Обработка ключа: {key}, значение: {value}, тип: {type(value)}")
        
        if value is None:
            logger.info(f"Значение None для ключа {key}, заменяем на пустую строку")
            cleaned[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            # Дополнительная проверка перед преобразованием
            try:
                logger.info(f"Преобразуем нестандартный тип {type(value)} в строку для ключа {key}")
                str_value = str(value)
                cleaned[key] = str_value
                logger.info(f"Успешно преобразовано в: {str_value}")
            except Exception as e:
                logger.error(f"Не удалось преобразовать значение для ключа {key}: {str(e)}")
                cleaned[key] = "ERROR_CONVERTING"
    
    logger.info(f"Результат очистки метаданных: {cleaned}")
    return cleaned


class VectorStoreService:
    """Сервис для работы с векторной базой данных."""
    
    def __init__(
        self,
        collection_name: str = "jarvis",
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """
        Инициализация сервиса векторной базы данных.
        
        Args:
            collection_name: Название коллекции в ChromaDB
            embedding_model_name: Название модели эмбеддингов из HuggingFace
        """
        self.collection_name = collection_name
        self.persist_directory = CHROMA_PERSIST_DIRECTORY
        
        # Создаем директорию для хранения векторной БД, если она не существует
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Инициализация модели эмбеддингов
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model_name,
        )
        
        # Инициализация векторной базы данных
        self.db = self._initialize_vector_db()
    
    def _initialize_vector_db(self) -> Chroma:
        """Инициализирует и возвращает экземпляр ChromaDB."""
        try:
            return Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
        except Exception as e:
            logger.error(f"Ошибка при инициализации ChromaDB: {str(e)}")
            raise
    
    async def add_texts(
        self, 
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Добавляет тексты в векторную базу данных.
        
        Args:
            texts: Список текстов для добавления
            metadatas: Список метаданных для каждого текста
            ids: Список идентификаторов для каждого текста
        
        Returns:
            Список идентификаторов добавленных текстов
        """
        try:
            # Логируем входные данные
            logger.info(f"Попытка добавить тексты в ChromaDB. Количество текстов: {len(texts)}")
            logger.info(f"Тексты: {texts}")
            logger.info(f"Метаданные: {metadatas}")
            
            # Проверяем каждый текст на None
            for i, text in enumerate(texts):
                if text is None:
                    logger.error(f"Текст с индексом {i} равен None")
            
            # Очищаем метаданные от None значений
            cleaned_metadatas = None
            if metadatas:
                logger.info("Начало очистки метаданных")
                cleaned_metadatas = []
                for i, meta in enumerate(metadatas):
                    logger.info(f"Очистка метаданных [{i}]: {meta}")
                    try:
                        cleaned_meta = clean_metadata(meta)
                        cleaned_metadatas.append(cleaned_meta)
                        logger.info(f"Успешно очищены метаданные [{i}]: {cleaned_meta}")
                    except Exception as meta_e:
                        logger.error(f"Ошибка при очистке метаданных [{i}]: {meta}, ошибка: {str(meta_e)}")
                        # Вместо поднятия исключения, вставим пустой словарь
                        cleaned_metadatas.append({})
            
            logger.info(f"Очищенные метаданные: {cleaned_metadatas}")
            
            return self.db.add_texts(texts=texts, metadatas=cleaned_metadatas, ids=ids)
        except Exception as e:
            logger.error(f"Ошибка при добавлении текстов в ChromaDB: {str(e)}")
            # Добавим трассировку стека для более подробной информации об ошибке
            import traceback
            logger.error(f"Трассировка: {traceback.format_exc()}")
            # Не позволяем ошибке подняться дальше
            return []
        
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Выполняет поиск по схожести в векторной базе данных.
        
        Args:
            query: Текст запроса
            k: Количество результатов для возврата
            filter: Фильтр для поиска (используется для фильтрации по метаданным)
        
        Returns:
            Список документов с метаданными и содержимым
        """
        try:
            # Очищаем фильтр от None значений
            cleaned_filter = None
            if filter:
                cleaned_filter = clean_metadata(filter)
                
            docs = self.db.similarity_search(query=query, k=k, filter=cleaned_filter)
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in docs
            ]
        except Exception as e:
            logger.error(f"Ошибка при поиске в ChromaDB: {str(e)}")
            return []