"""
News API Service - FastAPI application with llama-index and Qdrant integration
"""
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import FastAPI, Query, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import time
import json
import asyncio
import schedule
from threading import Thread

# Import our modules
from feed_parser import Article, fetch_all_feeds, fetch_feed
from vector_store import NewsVectorStore
from config import RSS_FEEDS, API_HOST, API_PORT, API_WORKERS
from request_tracker import RequestTrackerMiddleware, get_recent_requests

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
logger = logging.getLogger("news_api")

# Initialize FastAPI app
app = FastAPI(
    title="News API",
    description="API for fetching and processing news from various RSS feeds",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Add request tracker middleware
app.add_middleware(RequestTrackerMiddleware)

# Initialize vector store
vector_store = NewsVectorStore()

# Background task for fetching news
def fetch_news_task():
    """Background task to fetch news and update the vector store"""
    logger.info("Starting news fetch task")
    try:
        # Fetch all feeds
        articles = fetch_all_feeds()
        logger.info(f"Fetched {len(articles)} articles from all feeds")
        
        # Add articles to vector store
        vector_store.add_articles(articles)
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

# API Models
class ArticleModel(BaseModel):
    """API model for an article"""
    id: str
    title: str
    content: str
    summary: str
    url: str
    source: str
    published_date: str
    author: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None

class ArticleResponse(BaseModel):
    """API response model for articles"""
    articles: List[ArticleModel]
    count: int
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class SourcesResponse(BaseModel):
    """API response model for sources"""
    sources: List[str]
    count: int

class CategoriesResponse(BaseModel):
    """API response model for categories"""
    categories: List[str]
    count: int

class SearchQuery(BaseModel):
    """API model for search queries"""
    query: str
    limit: int = 10
    source: Optional[str] = None
    category: Optional[str] = None

# API Endpoints
@app.get("/api/monitoring/requests", response_model=Dict[str, Any])
async def get_api_requests():
    """Get recent API requests for monitoring"""
    return {
        "requests": get_recent_requests(),
        "count": len(get_recent_requests()),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/monitoring/stats", response_model=Dict[str, Any])
async def get_stats():
    """Get statistics about articles in the vector store"""
    try:
        # Get total article count (using an empty query)
        all_articles = vector_store.search("", limit=10000)
        total_count = len(all_articles)
        
        # Get articles added today
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_articles = [a for a in all_articles 
                         if datetime.fromisoformat(a["published_date"]) >= today]
        today_count = len(today_articles)
        
        # Get sources statistics
        sources = {}
        for article in all_articles:
            source = article.get("source")
            if source:
                sources[source] = sources.get(source, 0) + 1
        
        # Get categories statistics
        categories = {}
        for article in all_articles:
            for category in article.get("categories", []):
                if category:
                    categories[category] = categories.get(category, 0) + 1
        
        return {
            "total_articles": total_count,
            "articles_today": today_count,
            "sources": sources,
            "categories": categories,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_model=Dict[str, Any])
async def root():
    """Root endpoint"""
    return {
        "name": "News API",
        "version": "0.1.0",
        "description": "API for fetching and processing news from various RSS feeds with vector search",
        "endpoints": [
            "/api/news",
            "/api/news/sources",
            "/api/news/categories",
            "/api/news/search",
            "/api/news/source/{source}",
            "/api/news/category/{category}",
            "/api/news/fetch",  # Trigger manual fetch
        ],
    }

@app.get("/api/news", response_model=ArticleResponse)
async def get_news(
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    """Get recent news from all sources in the vector store"""
    try:
        # Use an empty query to get all articles
        articles = vector_store.search("", limit=limit + skip)
        
        # Apply pagination
        paginated_articles = articles[skip:skip + limit]
        
        return ArticleResponse(
            articles=[ArticleModel(**article) for article in paginated_articles],
            count=len(paginated_articles),
        )
    except Exception as e:
        logger.error(f"Error in get_news: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news/sources", response_model=SourcesResponse)
async def get_sources():
    """Get list of available news sources"""
    try:
        sources = vector_store.get_all_sources()
        return SourcesResponse(
            sources=sources,
            count=len(sources),
        )
    except Exception as e:
        logger.error(f"Error in get_sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news/categories", response_model=CategoriesResponse)
async def get_categories():
    """Get list of available news categories"""
    try:
        categories = vector_store.get_all_categories()
        return CategoriesResponse(
            categories=categories,
            count=len(categories),
        )
    except Exception as e:
        logger.error(f"Error in get_categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news/search", response_model=ArticleResponse)
async def search_news(
    query: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    source: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    """Search for news with specific keywords"""
    try:
        # Build filter dict
        filter_dict = {}
        if source:
            filter_dict["source"] = source
        if category:
            filter_dict["categories"] = category
        
        # Search in vector store
        articles = vector_store.search(query, limit=limit + skip, filter_dict=filter_dict)
        
        # Apply pagination
        paginated_articles = articles[skip:skip + limit]
        
        return ArticleResponse(
            articles=[ArticleModel(**article) for article in paginated_articles],
            count=len(paginated_articles),
        )
    except Exception as e:
        logger.error(f"Error in search_news: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news/source/{source}", response_model=ArticleResponse)
async def get_news_by_source(
    source: str,
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    """Get news from a specific source"""
    try:
        articles = vector_store.get_by_source(source, limit=limit + skip)
        
        # Apply pagination
        paginated_articles = articles[skip:skip + limit]
        
        return ArticleResponse(
            articles=[ArticleModel(**article) for article in paginated_articles],
            count=len(paginated_articles),
        )
    except Exception as e:
        logger.error(f"Error in get_news_by_source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news/category/{category}", response_model=ArticleResponse)
async def get_news_by_category(
    category: str,
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    """Get news filtered by category"""
    try:
        articles = vector_store.get_by_category(category, limit=limit + skip)
        
        # Apply pagination
        paginated_articles = articles[skip:skip + limit]
        
        return ArticleResponse(
            articles=[ArticleModel(**article) for article in paginated_articles],
            count=len(paginated_articles),
        )
    except Exception as e:
        logger.error(f"Error in get_news_by_category: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/news/fetch")
async def fetch_news(background_tasks: BackgroundTasks):
    """Trigger a manual fetch of news articles"""
    try:
        # Add fetch task to background tasks
        background_tasks.add_task(fetch_news_task)
        return {"message": "News fetch started in background"}
    except Exception as e:
        logger.error(f"Error in fetch_news: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Startup event
@app.on_event("startup")
async def startup_event():
    """Run when the API starts up"""
    # Fetch news on startup
    fetch_news_task()
    
    # Start scheduler for periodic fetching
    start_scheduler()

# Main entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=API_HOST, port=API_PORT, workers=API_WORKERS)
