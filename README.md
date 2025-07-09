# News RSS Feed Processor

A streamlined tool for fetching news from RSS feeds and storing them in your existing Qdrant vector database for semantic search and retrieval.

## Features

- Automatic fetching of news articles from multiple RSS feeds
- Storage in your existing Qdrant vector database
- Filter news by source, category, and keywords
- Scheduled updates to keep the news database current
- Simple REST API for querying articles
- Web-based monitoring UI to view logs and system status

## Architecture

This system consists of three main components:

1. **News Processor**: Fetches articles from RSS feeds, processes them, and stores them in Qdrant
2. **API Server**: Provides REST endpoints for searching and retrieving articles
3. **UI Server**: Web interface for monitoring logs and system status

All components connect to your existing Qdrant instance running on the host machine.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- An existing Qdrant instance running on the host machine (default: localhost:6333)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd news_man

# Start the services
docker-compose up -d
```

### Accessing the Services

- **Monitoring UI**: http://localhost:8428
- **API Server**: http://localhost:8427

## API Endpoints

### Search Articles

```
GET /api/search?query=<query>&limit=<limit>&source=<source>&category=<category>
```

Parameters:
- `query`: Search query (optional)
- `limit`: Maximum number of results (default: 10)
- `source`: Filter by source (optional)
- `category`: Filter by category (optional)

### Get Sources

```
GET /api/sources
```

Returns a list of all available sources.

### Get Categories

```
GET /api/categories
```

Returns a list of all available categories.

### Get Statistics

```
GET /api/stats
```

Returns statistics about the articles in the database.

### Get Article by ID

```
GET /api/article/<article_id>
```

Returns a specific article by its ID.

### Health Check

```
GET /health
```

Returns the health status of the API server.

## Configuration

### Environment Variables

You can configure the system using these environment variables in the docker-compose.yml file:

| Variable | Description | Default |
|----------|-------------|--------|
| `QDRANT_HOST` | Hostname of your Qdrant server | `host.docker.internal` |
| `QDRANT_PORT` | Port of your Qdrant server | `6333` |
| `QDRANT_COLLECTION` | Collection name in Qdrant | `news_articles` |
| `UPDATE_INTERVAL_HOURS` | How often to check for new articles | `6` |
| `INITIAL_DELAY_SECONDS` | Delay before first fetch on startup | `30` |
| `API_PORT` | Port for the API server | `8427` |

### RSS Feeds

The system is configured with several popular news sources by default. You can add or modify sources by editing the `RSS_FEEDS` dictionary in the `config.py` file.

## Customizing Qdrant Connection

If your Qdrant instance is running on a different host or port, update the environment variables in the docker-compose.simple.yml file:

```yaml
# Example: Custom Qdrant configuration
services:
  news-processor:
    environment:
      - QDRANT_HOST=192.168.1.100  # Your Qdrant server IP
      - QDRANT_PORT=6333           # Your Qdrant server port
      - QDRANT_COLLECTION=my_news  # Your collection name
```

The system will automatically create the collection if it doesn't exist in your Qdrant instance.

## Logs and Monitoring

The monitoring UI provides real-time log viewing and system status information. You can access it at http://localhost:8428.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
