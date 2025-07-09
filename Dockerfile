FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ .

# Create log directory
RUN mkdir -p /var/log/news_man
RUN touch /var/log/news_man/news_man.log
RUN chmod -R 777 /var/log/news_man

# Make the entrypoint script executable
RUN chmod +x entrypoint.py

# Environment variables
ENV UPDATE_INTERVAL_HOURS=6
ENV INITIAL_DELAY_SECONDS=10

# Command to run the weekly feed processor
CMD ["python", "entrypoint.py"]
