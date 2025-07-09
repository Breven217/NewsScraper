"""
Vector Store Module - A lightweight wrapper for Qdrant vector database

This module provides a VectorStore class that interfaces with Qdrant to store and
retrieve news articles as vector embeddings. It supports both regular news articles
and company news articles in separate collections.

The VectorStore uses SentenceTransformer to create embeddings from article text,
which are then stored in Qdrant for semantic search capabilities.
"""
import logging
import json
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer

from feed_parser import Article
from config import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_COLLECTION_NAME,
    EMBEDDING_MODEL_NAME
)
import os

# Override the vector size to match the existing collection
QDRANT_VECTOR_SIZE = 768

# Override the embedding model to match the vector size
EMBEDDING_MODEL_NAME = "all-mpnet-base-v2"  # This model produces 768-dimensional vectors

# Allow override of collection name via environment variable
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", QDRANT_COLLECTION_NAME)

# Add support for company news collection
COMPANY_COLLECTION_NAME = os.getenv("COMPANY_COLLECTION", "company_news_collection")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("vector_store")

class VectorStore:
    """A vector store for news articles using Qdrant"""
    
    def __init__(
        self,
        collection_name: str = COLLECTION_NAME,
        host: str = QDRANT_HOST,
        port: int = QDRANT_PORT,
        is_company_collection: bool = False
    ):
        """Initialize the vector store"""
        # Use company collection if specified
        if is_company_collection:
            collection_name = COMPANY_COLLECTION_NAME
            
        self.collection_name = collection_name
        self.client = QdrantClient(host=host, port=port)
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self.is_company_collection = is_company_collection
        
        # Create collection if it doesn't exist
        self._create_collection_if_not_exists()
        
        logger.info(f"Initialized VectorStore with collection: {collection_name} (Company: {is_company_collection})")
        
    @classmethod
    def get_company_store(cls, host: str = QDRANT_HOST, port: int = QDRANT_PORT):
        """Get a vector store for company news"""
        return cls(host=host, port=port, is_company_collection=True)
    
    def _create_collection_if_not_exists(self) -> None:
        """Create the collection if it doesn't exist"""
        collections = self.client.get_collections().collections
        collection_names = [collection.name for collection in collections]
        
        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=QDRANT_VECTOR_SIZE,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )
            logger.info(f"Created collection: {self.collection_name}")
    
    def _get_article_embedding(self, article: Article) -> List[float]:
        """Get the embedding for an article"""
        # Create a text representation of the article
        text = f"Title: {article.title}\n\nSummary: {article.summary}\n\nContent: {article.content}"
        
        # Get the embedding
        embedding = self.embedding_model.encode(text)
        
        return embedding.tolist()
    
    def _create_article_id(self, article: Article) -> str:
        """Create a unique ID for an article"""
        # Use the article's ID if available, otherwise create a hash
        if hasattr(article, 'id') and article.id:
            return article.id
        
        # Create a hash of the article URL, title, and published date
        hash_input = f"{article.url}|{article.title}|{article.published_date.isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _article_to_payload(self, article: Article) -> Dict[str, Any]:
        """Convert an article to a payload for Qdrant"""
        return {
            "id": self._create_article_id(article),
            "url": article.url,
            "title": article.title,
            "content": article.content,
            "summary": article.summary,
            "source": article.source,
            "categories": article.categories,
            "published_date": article.published_date.isoformat(),
            "image_url": article.image_url,
        }
    
    def add_articles(self, articles: List[Article]) -> None:
        """Add articles to the vector store"""
        if not articles:
            logger.warning("No articles to add to vector store")
            return
        
        # Process articles in batches to avoid memory issues
        batch_size = 10
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]
            
            # Create points for Qdrant
            points = []
            for article in batch:
                article_id = self._create_article_id(article)
                embedding = self._get_article_embedding(article)
                payload = self._article_to_payload(article)
                
                points.append(
                    qdrant_models.PointStruct(
                        id=article_id,
                        vector=embedding,
                        payload=payload
                    )
                )
            
            # Upsert points to Qdrant
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"Added {len(batch)} articles to vector store")
            except Exception as e:
                logger.error(f"Error adding articles to vector store: {e}")
    
    def search(
        self, 
        query: str, 
        limit: int = 10, 
        filter_dict: Optional[Dict[str, Any]] = None,
        min_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for articles in the vector store
        
        Args:
            query: Search query
            limit: Maximum number of results
            filter_dict: Filter criteria (e.g., {"source": "cnn"})
            min_score: Minimum relevance score to filter results
        
        Returns:
            List of articles matching the query
        """
        # Convert filter_dict to Qdrant filter
        filter_obj = None
        if filter_dict:
            filter_conditions = []
            for key, value in filter_dict.items():
                # Handle special date filtering
                if key == "published_date_filter":
                    # Date range filtering
                    if isinstance(value, dict):
                        # Create a DatetimeRange filter for proper datetime handling
                        # Qdrant supports RFC 3339 date formats directly
                        datetime_range_params = {}
                        
                        if "$lt" in value:
                            datetime_range_params["lt"] = value["$lt"]
                        if "$gt" in value:
                            datetime_range_params["gt"] = value["$gt"]
                        if "$gte" in value:
                            datetime_range_params["gte"] = value["$gte"]
                        if "$lte" in value:
                            datetime_range_params["lte"] = value["$lte"]
                            
                        # Add the datetime range filter condition
                        filter_conditions.append(
                            qdrant_models.FieldCondition(
                                key="published_date",
                                range=qdrant_models.DatetimeRange(
                                    **datetime_range_params
                                )
                            )
                        )
                elif isinstance(value, list):
                    # For lists (e.g., categories), check if any value matches
                    filter_conditions.append(
                        qdrant_models.FieldCondition(
                            key=key,
                            match=qdrant_models.MatchAny(any=value)
                        )
                    )
                else:
                    # For single values, use exact match
                    filter_conditions.append(
                        qdrant_models.FieldCondition(
                            key=key,
                            match=qdrant_models.MatchValue(value=value)
                        )
                    )
            
            # Combine all conditions with AND
            filter_obj = qdrant_models.Filter(
                must=filter_conditions
            )
        
        try:
            # Get embedding for query
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Search Qdrant
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=filter_obj,
                score_threshold=min_score
            )
            
            # Convert results to articles
            articles = []
            for result in search_results:
                article = result.payload
                article["score"] = result.score
                articles.append(article)
            
            return articles
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    def get_all_articles(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all articles from the vector store"""
        try:
            logger.info(f"Getting all articles from collection {self.collection_name}")
            
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                logger.error(f"Collection {self.collection_name} does not exist")
                return []
            
            # Get collection info to check if it has points
            collection_info = self.client.get_collection(self.collection_name)
            points_count = collection_info.points_count
            logger.info(f"Collection {self.collection_name} has {points_count} points")
            
            if points_count == 0:
                logger.warning(f"Collection {self.collection_name} is empty")
                return []
            
            # Use scroll to get all articles with pagination to avoid timeout
            articles = []
            offset = None
            page_size = 100  # Process in smaller batches
            
            while True:
                scroll_results = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=page_size,
                    with_vectors=False,
                    offset=offset
                )
                
                # Check if we got any results
                if not scroll_results[0]:
                    break
                
                # Convert results to articles
                for result in scroll_results[0]:
                    articles.append(result.payload)
                
                # Update offset for next page
                if len(scroll_results[0]) < page_size:
                    break
                    
                offset = scroll_results[1]  # Next offset
                
                # Safety check to avoid infinite loops
                if len(articles) >= limit:
                    break
            
            logger.info(f"Retrieved {len(articles)} articles from collection {self.collection_name}")
            return articles
        except Exception as e:
            logger.error(f"Error getting all articles: {e}")
            return []
    
    def get_article_by_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get an article by ID"""
        try:
            # Get article by ID
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[article_id]
            )
            
            if result:
                return result[0].payload
            
            return None
        except Exception as e:
            logger.error(f"Error getting article by ID: {e}")
            return None
