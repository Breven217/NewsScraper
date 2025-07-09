"""
Weekly Feed Processor - Fetches and stores articles from the last week
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set

from feed_parser import Article, fetch_all_feeds, fetch_feed
from vector_store import NewsVectorStore
from config import RSS_FEEDS

# Get log file path from environment variable or use default
LOG_FILE = os.getenv("LOG_FILE", "/var/log/news_man/news_man.log")

# Ensure log directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("weekly_feed_processor")

class WeeklyFeedProcessor:
    """Process RSS feeds and store articles from the last week"""
    
    def __init__(self, vector_store: Optional[NewsVectorStore] = None):
        """Initialize the weekly feed processor"""
        self.vector_store = vector_store or NewsVectorStore()
        
    def process_feeds(self) -> Dict[str, Any]:
        """
        Process all feeds and store articles from the last week
        
        Returns:
            Dictionary with processing statistics
        """
        # Get the date one week ago
        one_week_ago = datetime.now() - timedelta(days=7)
        logger.info(f"Fetching articles published after {one_week_ago.isoformat()}")
        
        # Fetch all articles
        all_articles = fetch_all_feeds()
        logger.info(f"Fetched {len(all_articles)} articles in total")
        
        # Filter articles by date (last week)
        recent_articles = [
            article for article in all_articles
            if article.published_date >= one_week_ago
        ]
        logger.info(f"Found {len(recent_articles)} articles from the last week")
        
        # Get existing article IDs from Qdrant
        existing_ids = self._get_existing_article_ids()
        logger.info(f"Found {len(existing_ids)} existing articles in the database")
        
        # Filter out articles that already exist in the database
        new_articles = [
            article for article in recent_articles
            if article.id not in existing_ids
        ]
        logger.info(f"Found {len(new_articles)} new articles to add to the database")
        
        # Add new articles to the vector store
        if new_articles:
            self.vector_store.add_articles(new_articles)
            logger.info(f"Added {len(new_articles)} new articles to the vector store")
        else:
            logger.info("No new articles to add to the vector store")
        
        # Return statistics
        return {
            "total_fetched": len(all_articles),
            "recent_articles": len(recent_articles),
            "existing_articles": len(existing_ids),
            "new_articles_added": len(new_articles),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_existing_article_ids(self) -> Set[str]:
        """
        Get IDs of existing articles in the vector store
        
        Returns:
            Set of article IDs
        """
        try:
            # Use an empty query to get all articles
            # This is not efficient for large databases, but works for demonstration
            # In a real implementation, you would use a more efficient approach
            all_articles = self.vector_store.search("", limit=10000)
            return {article["id"] for article in all_articles}
        except Exception as e:
            logger.error(f"Error getting existing article IDs: {e}")
            return set()

if __name__ == "__main__":
    # Process feeds
    processor = WeeklyFeedProcessor()
    stats = processor.process_feeds()
    
    # Print statistics
    print("\nProcessing complete!")
    print(f"Total articles fetched: {stats['total_fetched']}")
    print(f"Articles from the last week: {stats['recent_articles']}")
    print(f"Existing articles in database: {stats['existing_articles']}")
    print(f"New articles added: {stats['new_articles_added']}")
    print(f"Timestamp: {stats['timestamp']}")
