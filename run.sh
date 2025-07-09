#!/bin/bash

# Script to build and run the News API service

# Function to display usage
show_usage() {
  echo "Usage: $0 [build|start|stop|restart|logs|test]"
  echo ""
  echo "Commands:"
  echo "  build   - Build the Docker image"
  echo "  start   - Start the service"
  echo "  stop    - Stop the service"
  echo "  restart - Restart the service"
  echo "  logs    - View service logs"
  echo "  test    - Run test queries against the API"
}

# Function to test the API
test_api() {
  echo "Testing News API endpoints..."
  echo ""
  
  echo "1. Testing root endpoint:"
  curl -s http://localhost:8427/ | jq
  echo ""
  
  echo "2. Testing news endpoint:"
  curl -s "http://localhost:8427/api/news?limit=3" | jq
  echo ""
  
  echo "3. Testing sources endpoint:"
  curl -s http://localhost:8427/api/news/sources | jq
  echo ""
  
  echo "4. Testing search endpoint:"
  curl -s "http://localhost:8427/api/news/search?query=technology&limit=3" | jq
  echo ""
}

# Check if command is provided
if [ $# -eq 0 ]; then
  show_usage
  exit 1
fi

# Process command
case "$1" in
  build)
    echo "Building Docker image..."
    docker-compose build
    ;;
  start)
    echo "Starting News API service..."
    docker-compose up -d
    echo "Service started at http://localhost:8427"
    ;;
  stop)
    echo "Stopping News API service..."
    docker-compose down
    ;;
  restart)
    echo "Restarting News API service..."
    docker-compose restart
    ;;
  logs)
    echo "Showing logs for News API service..."
    docker-compose logs -f
    ;;
  test)
    test_api
    ;;
  *)
    show_usage
    exit 1
    ;;
esac
