"""
Configuration settings for the news manager
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Default RSS feeds to parse
RSS_FEEDS = {
    # General News
    "cnn": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "bbc": "http://feeds.bbci.co.uk/news/rss.xml",
    "reuters": "http://feeds.reuters.com/reuters/topNews",
    "ap": "https://feeds.ap.org/rss/topnews",
    
    # Technology News
    "wired": "https://www.wired.com/feed/rss",
    "techcrunch": "https://techcrunch.com/feed/",
    "ars_technica": "http://feeds.arstechnica.com/arstechnica/index",
    
    # Business News
    "wsj": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    "bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
    "financial_times": "https://www.ft.com/?format=rss",
    
    # Science News
    "science_daily": "https://www.sciencedaily.com/rss/all.xml",
    "nature": "http://feeds.nature.com/nature/rss/current",
    
    # Health News
    "who": "https://www.who.int/rss-feeds/news-english.xml",
    "health_news": "https://medicalxpress.com/rss-feed/",
}

# Maximum number of articles to fetch per feed
MAX_ARTICLES_PER_FEED = 10

# Request settings
REQUEST_TIMEOUT = 10  # seconds
USER_AGENT = "NewsMan/0.1.0"

# Content cleaning settings
REMOVE_HTML_TAGS = True
MAX_SUMMARY_LENGTH = 200  # characters

# Qdrant settings
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "news_articles")
QDRANT_VECTOR_SIZE = 768  # For sentence-transformers default models

# Date filtering settings
ARTICLE_MAX_AGE_DAYS = int(os.getenv("ARTICLE_MAX_AGE_DAYS", "7"))  # Default to 1 week

# Embedding model settings
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# API settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_WORKERS = int(os.getenv("API_WORKERS", "4"))

# Cache settings
CACHE_DIR = os.getenv("CACHE_DIR", "/tmp/news_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
