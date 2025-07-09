"""
RSS Feed Fetcher - Demonstrates fetching RSS feeds and querying the Qdrant database
"""
import logging
import time
from typing import List, Dict, Any
import argparse

from app_simplified import (
    fetch_news_task,
    search_articles,
    get_articles_by_source,
    get_articles_by_category,
    get_all_sources,
    get_all_categories
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("rss_fetcher")

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

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="RSS Feed Fetcher")
    parser.add_argument("--fetch", action="store_true", help="Fetch new articles from RSS feeds")
    parser.add_argument("--search", type=str, help="Search for articles with query")
    parser.add_argument("--source", type=str, help="Filter by source")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--list-sources", action="store_true", help="List all sources")
    parser.add_argument("--list-categories", action="store_true", help="List all categories")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of results")
    
    args = parser.parse_args()
    
    if args.fetch:
        logger.info("Fetching articles from RSS feeds...")
        fetch_news_task()
        logger.info("Fetch completed")
    
    if args.list_sources:
        sources = get_all_sources()
        print("\nAvailable sources:")
        for source in sources:
            print(f"- {source}")
    
    if args.list_categories:
        categories = get_all_categories()
        print("\nAvailable categories:")
        for category in categories:
            print(f"- {category}")
    
    if args.search:
        print(f"\nSearching for '{args.search}':")
        articles = search_articles(
            query=args.search,
            limit=args.limit,
            source=args.source,
            category=args.category
        )
        
        if not articles:
            print("No articles found")
        else:
            for article in articles:
                print_article(article)
    
    elif args.source and not args.search:
        print(f"\nArticles from source '{args.source}':")
        articles = get_articles_by_source(args.source, limit=args.limit)
        
        if not articles:
            print("No articles found")
        else:
            for article in articles:
                print_article(article)
    
    elif args.category and not args.search:
        print(f"\nArticles in category '{args.category}':")
        articles = get_articles_by_category(args.category, limit=args.limit)
        
        if not articles:
            print("No articles found")
        else:
            for article in articles:
                print_article(article)

if __name__ == "__main__":
    main()
