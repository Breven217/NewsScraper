"""
News API Client - A Python client for the News API service
"""
import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

class NewsAPIClient:
    """Client for the News API service"""
    
    def __init__(self, base_url: str = "http://localhost:8427"):
        """Initialize the News API client"""
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    def get_news(self, limit: int = 10, skip: int = 0) -> Dict[str, Any]:
        """Get recent news from all sources"""
        url = f"{self.base_url}/api/news"
        params = {"limit": limit, "skip": skip}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_sources(self) -> Dict[str, Any]:
        """Get list of available news sources"""
        url = f"{self.base_url}/api/news/sources"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_categories(self) -> Dict[str, Any]:
        """Get list of available news categories"""
        url = f"{self.base_url}/api/news/categories"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def search_news(self, query: str, limit: int = 10, skip: int = 0, 
                   source: Optional[str] = None, category: Optional[str] = None) -> Dict[str, Any]:
        """Search for news with specific keywords"""
        url = f"{self.base_url}/api/news/search"
        params = {
            "query": query,
            "limit": limit,
            "skip": skip
        }
        if source:
            params["source"] = source
        if category:
            params["category"] = category
            
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_news_by_source(self, source: str, limit: int = 10, skip: int = 0) -> Dict[str, Any]:
        """Get news from a specific source"""
        url = f"{self.base_url}/api/news/source/{source}"
        params = {"limit": limit, "skip": skip}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_news_by_category(self, category: str, limit: int = 10, skip: int = 0) -> Dict[str, Any]:
        """Get news filtered by category"""
        url = f"{self.base_url}/api/news/category/{category}"
        params = {"limit": limit, "skip": skip}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def fetch_news(self) -> Dict[str, Any]:
        """Trigger a manual fetch of news articles"""
        url = f"{self.base_url}/api/news/fetch"
        response = self.session.post(url)
        response.raise_for_status()
        return response.json()


def print_article(article: Dict[str, Any]) -> None:
    """Print article in a readable format"""
    print(f"Title: {article['title']}")
    print(f"Source: {article['source']}")
    print(f"Published: {article['published_date']}")
    print(f"URL: {article['url']}")
    if article.get('categories'):
        print(f"Categories: {', '.join(article['categories'])}")
    print(f"Summary: {article['summary']}")
    print("-" * 80)


if __name__ == "__main__":
    # Initialize client
    client = NewsAPIClient()
    
    try:
        # Trigger a fetch (this will run in the background on the server)
        print("Triggering news fetch...")
        result = client.fetch_news()
        print(f"Result: {result}")
        print("\nWaiting a few seconds for fetch to complete...")
        import time
        time.sleep(5)  # Wait for fetch to complete
        
        # Get available sources
        print("\nAvailable news sources:")
        sources = client.get_sources()
        for source in sources["sources"]:
            print(f"- {source}")
        
        # Get available categories
        print("\nAvailable news categories:")
        categories = client.get_categories()
        for category in categories["categories"]:
            print(f"- {category}")
        
        # Get recent news
        print("\nRecent news:")
        news = client.get_news(limit=3)
        for article in news["articles"]:
            print_article(article)
        
        # Search for news
        query = "technology"
        print(f"\nSearching for '{query}':")
        search_results = client.search_news(query, limit=3)
        for article in search_results["articles"]:
            print_article(article)
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure the News API server is running!")
