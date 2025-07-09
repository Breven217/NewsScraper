#!/usr/bin/env python3
"""
Simple Docker entrypoint script for the News RSS Feed Processor
This script runs when the Docker container starts and:
1. Fetches articles from the last week
2. Stores only new articles in Qdrant
3. Runs a scheduler to periodically update the database
"""
import os
import time
import logging
import schedule
from threading import Thread
from datetime import datetime

from weekly_processor import WeeklyProcessor

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
logger = logging.getLogger("simple_entrypoint")

# Environment variables
UPDATE_INTERVAL_HOURS = int(os.getenv("UPDATE_INTERVAL_HOURS", "1"))
INITIAL_DELAY_SECONDS = int(os.getenv("INITIAL_DELAY_SECONDS", "10"))

def process_feeds_task():
    """Task to process feeds and store articles"""
    logger.info("Starting feed processing task")
    try:
        processor = WeeklyProcessor()
        stats = processor.process_feeds()
        
        logger.info(f"Processing complete! Added {stats['new_articles_added']} new articles to the database")
        return stats
    except Exception as e:
        logger.error(f"Error in process_feeds_task: {e}")
        return None

def start_scheduler():
    """Start the scheduler for periodic feed processing"""
    # Schedule the task to run at the specified interval
    schedule.every(UPDATE_INTERVAL_HOURS).hours.do(process_feeds_task)
    logger.info(f"Scheduler started, will process feeds every {UPDATE_INTERVAL_HOURS} hours")
    
    # Run in a separate thread
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    thread = Thread(target=run_scheduler, daemon=True)
    thread.start()
    return thread

if __name__ == "__main__":
    logger.info("Starting Simple News RSS Feed Processor Docker container")
    
    # Wait for a short time to ensure all services are ready
    logger.info(f"Waiting {INITIAL_DELAY_SECONDS} seconds before initial processing...")
    time.sleep(INITIAL_DELAY_SECONDS)
    
    # Process feeds on startup
    logger.info("Performing initial feed processing...")
    process_feeds_task()
    
    # Start scheduler for periodic updates
    scheduler_thread = start_scheduler()
    
    # Keep the main thread alive
    try:
        while True:
            logger.info("News RSS Feed Processor is running. Press Ctrl+C to stop.")
            time.sleep(3600)  # Log status every hour
    except KeyboardInterrupt:
        logger.info("News RSS Feed Processor stopped by user")
