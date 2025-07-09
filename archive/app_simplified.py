"""
News RSS Feed Processor - Fetches RSS feeds and stores articles in Qdrant
"""
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import time
import schedule
from threading import Thread

# Import our modules
from feed_parser import Article, fetch_all_feeds, fetch_feed
from vector_store import NewsVectorStore
from config import RSS_FEEDS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_processor")

# Initialize vector store
vector_store = NewsVectorStore()

# Function to fetch news and update the vector store
def fetch_news_task():
    """Fetch news from RSS feeds and update the vector store"""
    logger.info("Starting news fetch task")
    try:
        # Fetch all feeds
        articles = fetch_all_feeds()
        logger.info(f"Fetched {len(articles)} articles from all feeds")
        
        # Add articles to vector store
        vector_store.add_articles(articles)
        logger.info(f"Added {len(articles)} articles to vector store")
    except Exception as e:
        logger.error(f"Error in fetch_news_task: {e}")

# Schedule periodic news fetching
def start_scheduler():
    """Start the scheduler for periodic tasks"""
    schedule.every(1).hours.do(fetch_news_task)
    
    # Run in a separate thread
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    thread = Thread(target=run_scheduler, daemon=True)
    thread.start()
    logger.info("Scheduler started for periodic news fetching")

# Function to search articles in the vector store
def search_articles(query: str, limit: int = 10, source: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search for articles in the vector store
    
    Args:
        query: Search query
        limit: Maximum number of results
        source: Filter by source
        category: Filter by category
        
    Returns:
        List of article dictionaries
    """
    # Build filter dict
    filter_dict = {}
    if source:
        filter_dict["source"] = source
    if category:
        filter_dict["categories"] = category
    
    # Search in vector store
    return vector_store.search(query, limit=limit, filter_dict=filter_dict)

# Function to get articles by source
def get_articles_by_source(source: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get articles from a specific source
    
    Args:
        source: Source name
        limit: Maximum number of results
        
    Returns:
        List of article dictionaries
    """
    return vector_store.get_by_source(source, limit=limit)

# Function to get articles by category
def get_articles_by_category(category: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get articles filtered by category
    
    Args:
        category: Category name
        limit: Maximum number of results
        
    Returns:
        List of article dictionaries
    """
    return vector_store.get_by_category(category, limit=limit)

# Function to get all sources
def get_all_sources() -> List[str]:
    """
    Get all unique sources in the vector store
    
    Returns:
        List of source names
    """
    return vector_store.get_all_sources()

# Function to get all categories
def get_all_categories() -> List[str]:
    """
    Get all unique categories in the vector store
    
    Returns:
        List of category names
    """
    return vector_store.get_all_categories()

# Main entry point
if __name__ == "__main__":
    # Fetch news on startup
    logger.info("Starting news processor")
    fetch_news_task()
    
    # Start scheduler for periodic fetching
    start_scheduler()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(3600)  # Sleep for an hour
    except KeyboardInterrupt:
        logger.info("News processor stopped by user")
