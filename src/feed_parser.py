"""
Module for parsing RSS feeds and extracting articles
"""
import logging
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Optional
from dateutil import parser as date_parser
import time
import json
import os
from urllib.parse import urlparse
import re

from config import (
    RSS_FEEDS,
    MAX_ARTICLES_PER_FEED,
    REQUEST_TIMEOUT,
    USER_AGENT,
    REMOVE_HTML_TAGS,
    MAX_SUMMARY_LENGTH,
    CACHE_DIR
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("feed_parser")

# Initialize HTTP session
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


class Article:
    """Class representing a news article"""
    def __init__(
        self,
        title: str,
        content: str,
        summary: str,
        url: str,
        source: str,
        published_date: datetime,
        id: Optional[str] = None,
        author: Optional[str] = None,
        categories: List[str] = None,
        image_url: Optional[str] = None,
    ):
        self.id = id
        self.title = title
        self.content = content
        self.summary = summary
        self.url = url
        self.source = source
        self.published_date = published_date
        self.author = author
        self.categories = categories or []
        self.image_url = image_url
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert article to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published_date": self.published_date.isoformat(),
            "author": self.author,
            "categories": self.categories,
            "image_url": self.image_url,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Article':
        """Create article from dictionary"""
        # Convert ISO format date string back to datetime
        if isinstance(data.get("published_date"), str):
            data["published_date"] = datetime.fromisoformat(data["published_date"])
        return cls(**data)


def clean_html(html_content: str) -> str:
    """Remove HTML tags from content"""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def extract_image_from_content(content: str) -> Optional[str]:
    """Extract image URL from HTML content"""
    if not content:
        return None
    try:
        soup = BeautifulSoup(content, "html.parser")
        img = soup.find("img")
        if img and img.has_attr("src"):
            return img["src"]
    except Exception as e:
        logger.error(f"Error extracting image: {e}")
    return None


def categorize_by_url(url: str) -> List[str]:
    """Attempt to categorize an article based on its URL"""
    categories = []
    
    # Parse URL
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    
    # Check path components
    path_parts = [p for p in path.split("/") if p]
    
    # Common category names in URLs
    common_categories = {
        "tech": ["tech", "technology", "digital", "gadgets", "computers", "software", "ai"],
        "business": ["business", "finance", "economy", "markets", "money", "investing"],
        "politics": ["politics", "government", "election", "policy", "congress"],
        "health": ["health", "medical", "medicine", "wellness", "covid", "disease"],
        "science": ["science", "research", "space", "environment", "climate"],
        "sports": ["sports", "football", "soccer", "basketball", "baseball", "nfl", "nba", "mlb"],
        "entertainment": ["entertainment", "movies", "tv", "music", "celebrity", "hollywood"],
        "world": ["world", "international", "global", "europe", "asia", "africa"],
    }
    
    # Check each path part against common categories
    for part in path_parts:
        for category, keywords in common_categories.items():
            if part in keywords:
                categories.append(category)
                break
                
    return list(set(categories))  # Remove duplicates


def get_cache_path(source: str) -> str:
    """Get cache file path for a source"""
    return os.path.join(CACHE_DIR, f"{source}.json")


def get_from_cache(source: str) -> List[Dict[str, Any]]:
    """Get articles from cache"""
    cache_path = get_cache_path(source)
    
    if not os.path.exists(cache_path):
        return []
        
    try:
        with open(cache_path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error reading cache for {source}: {e}")
        return []


def save_to_cache(source: str, articles: List[Dict[str, Any]]) -> None:
    """Save articles to cache"""
    cache_path = get_cache_path(source)
    
    try:
        with open(cache_path, "w") as f:
            json.dump(articles, f, default=str)
    except Exception as e:
        logger.error(f"Error saving cache for {source}: {e}")


def create_article_id(url: str, title: str, published_date: datetime) -> str:
    """Create a unique ID for an article"""
    # Use URL path, title, and date to create a unique ID
    parsed_url = urlparse(url)
    path = parsed_url.path
    
    # Create a string that combines these elements
    id_string = f"{path}_{title}_{published_date.isoformat()}"
    
    # Create a hash of this string
    import hashlib
    return hashlib.md5(id_string.encode()).hexdigest()


def parse_entry(entry, source: str) -> Optional[Article]:
    """Parse a feed entry into an Article object"""
    # Get title
    title = getattr(entry, "title", "")
    if not title:
        return None
        
    # Get URL
    url = getattr(entry, "link", "")
    if not url:
        return None
        
    # Get content
    content = ""
    if hasattr(entry, "content"):
        content = entry.content[0].value
    elif hasattr(entry, "description"):
        content = entry.description
    elif hasattr(entry, "summary"):
        content = entry.summary
        
    # Clean content if needed
    if REMOVE_HTML_TAGS and content:
        content = clean_html(content)
        
    # Get summary
    summary = getattr(entry, "summary", content)
    if REMOVE_HTML_TAGS and summary:
        summary = clean_html(summary)
        
    # Truncate summary if needed
    if summary and len(summary) > MAX_SUMMARY_LENGTH:
        summary = summary[:MAX_SUMMARY_LENGTH] + "..."
        
    # Get published date
    published_date = datetime.now()
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        published_date = datetime(*entry.published_parsed[:6])
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        published_date = datetime(*entry.updated_parsed[:6])
    elif hasattr(entry, "published") and entry.published:
        try:
            published_date = date_parser.parse(entry.published)
        except Exception:
            pass
    elif hasattr(entry, "updated") and entry.updated:
        try:
            published_date = date_parser.parse(entry.updated)
        except Exception:
            pass
            
    # Get author
    author = None
    if hasattr(entry, "author"):
        author = entry.author
        
    # Get categories
    categories = []
    if hasattr(entry, "tags"):
        categories = [tag.term for tag in entry.tags if hasattr(tag, "term")]
    elif hasattr(entry, "categories"):
        categories = list(entry.categories)
        
    # If no categories, try to extract from URL
    if not categories:
        categories = categorize_by_url(url)
        
    # Get image URL
    image_url = None
    if hasattr(entry, "media_content") and entry.media_content:
        for media in entry.media_content:
            if "url" in media and ("image" in media.get("type", "") or media.get("medium") == "image"):
                image_url = media["url"]
                break
                
    # If no image found, try to extract from content
    if not image_url and content:
        image_url = extract_image_from_content(content)
    
    # Create a unique ID for the article
    article_id = create_article_id(url, title, published_date)
        
    return Article(
        id=article_id,
        title=title,
        content=content,
        summary=summary,
        url=url,
        source=source,
        published_date=published_date,
        author=author,
        categories=categories,
        image_url=image_url
    )


def fetch_feed(source: str, url: str, max_articles: int = None) -> List[Article]:
    """Fetch and parse an RSS feed"""
    max_articles = max_articles or MAX_ARTICLES_PER_FEED
    
    # Fetch the feed
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        feed = feedparser.parse(response.content)
    except Exception as e:
        logger.error(f"Error fetching feed {source} ({url}): {e}")
        return []
    
    articles = []
    for entry in feed.entries[:max_articles]:
        try:
            article = parse_entry(entry, source)
            if article:
                articles.append(article)
        except Exception as e:
            logger.error(f"Error parsing entry from {source}: {e}")
    
    # Update cache
    if articles:
        save_to_cache(source, [article.to_dict() for article in articles])
        
    return articles


def fetch_all_feeds(feeds: Dict[str, str] = None) -> List[Article]:
    """Fetch all configured feeds"""
    feeds = feeds or RSS_FEEDS
    all_articles = []
    
    for source, url in feeds.items():
        try:
            source_articles = fetch_feed(source, url)
            all_articles.extend(source_articles)
            logger.info(f"Fetched {len(source_articles)} articles from {source}")
        except Exception as e:
            logger.error(f"Error fetching feed {source} ({url}): {e}")
    
    # Sort by published date (newest first)
    all_articles.sort(key=lambda x: x.published_date, reverse=True)
    
    return all_articles
