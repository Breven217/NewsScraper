"""
Simple API Server - A lightweight API for querying news articles

This module provides a Flask-based REST API for interacting with the news articles
stored in the vector database. It supports both regular news articles and company news.
"""
import os
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from vector_store import VectorStore
import hashlib

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
logger = logging.getLogger("api")

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize vector stores
vector_store = VectorStore()
company_vector_store = VectorStore.get_company_store()

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

# Helper functions for common operations
def build_filter_dict(source: Optional[str] = None, 
                     category: Optional[str] = None,
                     date: Optional[str] = None,
                     date_operand: str = "on") -> Dict[str, Any]:
    """
    Build a filter dictionary for vector store queries
    
    Args:
        source: Optional source filter
        category: Optional category filter
        date: Optional date filter (ISO format)
        date_operand: Date comparison operator (on, before, after, etc.)
        
    Returns:
        Dictionary with filter criteria
    """
    filter_dict = {}
    
    # Add source filter if provided
    if source:
        filter_dict["source"] = source
        
    # Add category filter if provided
    if category:
        filter_dict["categories"] = [category]
    
    # Handle date filtering
    if date:
        try:
            # Parse the date string
            filter_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
            
            # Apply date filter based on operand
            if date_operand == "before":
                filter_dict["published_date_filter"] = {"$lt": filter_date.isoformat()}
            elif date_operand == "after":
                filter_dict["published_date_filter"] = {"$gt": filter_date.isoformat()}
            elif date_operand == "on_or_before" or date_operand == "<=":
                filter_dict["published_date_filter"] = {"$lte": filter_date.isoformat()}
            elif date_operand == "on_or_after" or date_operand == ">=":
                filter_dict["published_date_filter"] = {"$gte": filter_date.isoformat()}
            else:  # "on" is the default
                # For "on", we'll consider the entire day
                start_of_day = filter_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = filter_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                filter_dict["published_date_filter"] = {
                    "$gte": start_of_day.isoformat(),
                    "$lte": end_of_day.isoformat()
                }
        except ValueError as e:
            # Return None to indicate an error in date parsing
            logger.error(f"Invalid date format: {e}")
            return None
            
    return filter_dict

def extract_unique_sources(articles: List[Dict[str, Any]]) -> List[str]:
    """
    Extract unique sources from a list of articles
    
    Args:
        articles: List of article dictionaries
        
    Returns:
        Sorted list of unique sources
    """
    sources = set()
    for article in articles:
        if "source" in article and article["source"]:
            sources.add(article["source"])
    return sorted(list(sources))

def extract_unique_categories(articles: List[Dict[str, Any]]) -> List[str]:
    """
    Extract unique categories from a list of articles
    
    Args:
        articles: List of article dictionaries
        
    Returns:
        Sorted list of unique categories
    """
    categories = set()
    for article in articles:
        if "categories" in article and article["categories"]:
            for category in article["categories"]:
                if category:
                    categories.add(category)
    return sorted(list(categories))

def create_error_response(message: str, status_code: int = 500) -> Tuple[Response, int]:
    """
    Create a standardized error response
    
    Args:
        message: Error message
        status_code: HTTP status code
        
    Returns:
        JSON response with error message and status code
    """
    return jsonify({
        "success": False,
        "error": message
    }), status_code

def count_articles_by_attribute(articles: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Count articles by source and category
    
    Args:
        articles: List of article dictionaries
        
    Returns:
        Tuple of (sources_count, categories_count) dictionaries
    """
    # Count articles by source
    sources = {}
    for article in articles:
        if "source" in article and article["source"]:
            source = article["source"]
            sources[source] = sources.get(source, 0) + 1
    
    # Count articles by category
    categories = {}
    for article in articles:
        if "categories" in article and article["categories"]:
            for category in article["categories"]:
                if category:
                    categories[category] = categories.get(category, 0) + 1
                    
    return sources, categories

@app.route("/api/search", methods=["GET"])
def search_articles():
    """Search for articles in the main collection"""
    # Get query parameters
    query = request.args.get("query", "")
    limit = int(request.args.get("limit", "10"))
    min_score = float(request.args.get("min_score", "0.35"))
    source = request.args.get("source")
    category = request.args.get("category")
    date = request.args.get("date")
    date_operand = request.args.get("date_operand", "on")  # on, before, after, on_or_before, on_or_after
    
    # Build filter dictionary
    filter_dict = build_filter_dict(source, category, date, date_operand)
    if filter_dict is None:  # Error in date parsing
        return create_error_response(
            "Invalid date format. Please use ISO format (YYYY-MM-DD)", 400
        )
    
    # Log the request
    logger.info(f"Search request: query='{query}', limit={limit}, min_score={min_score}, filter={filter_dict}")
    
    # Search for articles
    try:
        results = vector_store.search(query, limit=limit, filter_dict=filter_dict, min_score=min_score)
        return jsonify({
            "success": True,
            "count": len(results),
            "results": results
        })
    except Exception as e:
        logger.error(f"Error searching for articles: {e}")
        return create_error_response(str(e))

@app.route("/api/sources", methods=["GET"])
def get_sources():
    """Get all available sources from the main collection"""
    try:
        # Get all articles
        articles = vector_store.get_all_articles()
        
        # Extract unique sources
        sources = extract_unique_sources(articles)
        
        return jsonify({
            "success": True,
            "count": len(sources),
            "sources": sources
        })
    except Exception as e:
        logger.error(f"Error getting sources: {e}")
        return create_error_response(str(e))

@app.route("/api/categories", methods=["GET"])
def get_categories():
    """Get all available categories from the main collection"""
    try:
        logger.info("Getting categories from vector store")
        
        # Check if collection exists
        collections = vector_store.client.get_collections().collections
        collection_names = [c.name for c in collections]
        logger.info(f"Available collections: {collection_names}")
        
        if vector_store.collection_name not in collection_names:
            logger.error(f"Collection {vector_store.collection_name} does not exist")
            return create_error_response(
                f"Collection {vector_store.collection_name} does not exist", 404
            )
        
        # Get all articles
        articles = vector_store.get_all_articles()
        logger.info(f"Found {len(articles)} articles in collection")
        
        # Extract unique categories
        categories = extract_unique_categories(articles)
        
        logger.info(f"Found {len(categories)} unique categories")
        
        return jsonify({
            "success": True,
            "count": len(categories),
            "categories": categories
        })
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return create_error_response(str(e))

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get statistics about articles in the main collection"""
    try:
        # Get all articles
        articles = vector_store.get_all_articles()
        
        # Count articles by source and category
        sources, categories = count_articles_by_attribute(articles)
        
        # Count articles by date
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        articles_today = 0
        for article in articles:
            if "published_date" in article and article["published_date"]:
                try:
                    published_date = datetime.fromisoformat(article["published_date"])
                    if published_date >= today:
                        articles_today += 1
                except (ValueError, TypeError):
                    pass
        
        return jsonify({
            "success": True,
            "total_articles": len(articles),
            "articles_today": articles_today,
            "sources": sources,
            "categories": categories,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return create_error_response(str(e))

@app.route("/api/article/<article_id>", methods=["GET"])
def get_article(article_id):
    """Get an article by ID from the main collection"""
    try:
        article = vector_store.get_article_by_id(article_id)
        if article:
            return jsonify({
                "success": True,
                "article": article
            })
        else:
            return create_error_response("Article not found", 404)
    except Exception as e:
        logger.error(f"Error getting article: {e}")
        return create_error_response(str(e))

@app.route("/api/company/search", methods=["GET"])
def search_company_articles():
    """Search for articles in the company news collection"""
    # Get query parameters
    query = request.args.get("query", "")
    limit = int(request.args.get("limit", "10"))
    min_score = float(request.args.get("min_score", "0.35"))
    source = request.args.get("source")
    category = request.args.get("category")
    date = request.args.get("date")
    date_operand = request.args.get("date_operand", "on")  # on, before, after, on_or_before, on_or_after
    
    # Build filter dictionary
    filter_dict = build_filter_dict(source, category, date, date_operand)
    if filter_dict is None:  # Error in date parsing
        return create_error_response(
            "Invalid date format. Please use ISO format (YYYY-MM-DD)", 400
        )
    
    # Log the request
    logger.info(f"Company search request: query='{query}', limit={limit}, min_score={min_score}, filter={filter_dict}")
    
    # Search for articles
    try:
        results = company_vector_store.search(query, limit=limit, filter_dict=filter_dict, min_score=min_score)
        return jsonify({
            "success": True,
            "count": len(results),
            "results": results
        })
    except Exception as e:
        logger.error(f"Error searching for company articles: {e}")
        return create_error_response(str(e))

@app.route("/api/company/add", methods=["POST"])
def add_company_article():
    """Add a new article to the company news collection"""
    try:
        # Get article data from request
        data = request.json
        
        if not data:
            return create_error_response("No data provided", 400)
            
        # Create article object
        from feed_parser import Article
        
        # Required fields
        required_fields = ["title", "url", "summary"]
        for field in required_fields:
            if field not in data:
                return create_error_response(f"Missing required field: {field}", 400)
        
        # Create article with required fields
        article = Article(
            title=data["title"],
            url=data["url"],
            summary=data["summary"],
            content=data.get("content", data["summary"]),
            published_date=datetime.fromisoformat(data.get("published_date", datetime.now().isoformat())),
            source=data.get("source", "company"),
            categories=data.get("categories", ["company"]),
            image_url=data.get("image_url", "")
        )
        
        # Add article to vector store
        company_vector_store.add_articles([article])
        
        return jsonify({
            "success": True,
            "message": "Article added successfully",
            "article_id": company_vector_store._create_article_id(article)
        })
    except Exception as e:
        logger.error(f"Error adding company article: {e}")
        return create_error_response(str(e))

@app.route("/api/company/sources", methods=["GET"])
def get_company_sources():
    """Get all available sources from the company news collection"""
    try:
        # Get all articles
        articles = company_vector_store.get_all_articles()
        
        # Extract unique sources
        sources = extract_unique_sources(articles)
        
        return jsonify({
            "success": True,
            "count": len(sources),
            "sources": sources
        })
    except Exception as e:
        logger.error(f"Error getting company sources: {e}")
        return create_error_response(str(e))

@app.route("/api/company/categories", methods=["GET"])
def get_company_categories():
    """Get all available categories from the company news collection"""
    try:
        # Get all articles
        articles = company_vector_store.get_all_articles()
        
        # Extract unique categories
        categories = extract_unique_categories(articles)
        
        return jsonify({
            "success": True,
            "count": len(categories),
            "categories": categories
        })
    except Exception as e:
        logger.error(f"Error getting company categories: {e}")
        return create_error_response(str(e))

@app.route("/api/company/stats", methods=["GET"])
def get_company_stats():
    """Get statistics about articles in the company news collection"""
    try:
        # Get all articles
        articles = company_vector_store.get_all_articles()
        
        # Count total articles
        total_count = len(articles)
        
        # Count articles by source and category
        sources, categories = count_articles_by_attribute(articles)
        
        return jsonify({
            "success": True,
            "total_articles": total_count,
            "sources": sources,
            "categories": categories,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting company stats: {e}")
        return create_error_response(str(e))

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring system status"""
    try:
        # Check if vector stores are accessible
        main_collection_exists = vector_store.collection_name in [c.name for c in vector_store.client.get_collections().collections]
        company_collection_exists = company_vector_store.collection_name in [c.name for c in company_vector_store.client.get_collections().collections]
        
        # Get article counts
        main_articles_count = 0
        company_articles_count = 0
        
        if main_collection_exists:
            main_articles_count = vector_store.client.get_collection(vector_store.collection_name).points_count
        
        if company_collection_exists:
            company_articles_count = company_vector_store.client.get_collection(company_vector_store.collection_name).points_count
        
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "collections": {
                "main": {
                    "name": vector_store.collection_name,
                    "exists": main_collection_exists,
                    "articles_count": main_articles_count
                },
                "company": {
                    "name": company_vector_store.collection_name,
                    "exists": company_collection_exists,
                    "articles_count": company_articles_count
                }
            },
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return create_error_response(f"Health check failed: {e}", 500)

if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.getenv("API_PORT", "8427"))
    
    # Start Flask server
    app.run(host="0.0.0.0", port=port)
