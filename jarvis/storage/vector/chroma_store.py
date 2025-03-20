import os
from typing import List, Dict, Any, Optional, Union
import logging

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from jarvis.config import CHROMA_PERSIST_DIRECTORY, HUGGINGFACE_API_KEY

logger = logging.getLogger(__name__)


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
            return self.db.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        except Exception as e:
            logger.error(f"Ошибка при добавлении текстов в ChromaDB: {str(e)}")
            raise
    
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
            docs = self.db.similarity_search(query=query, k=k, filter=filter)
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
