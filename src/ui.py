"""
UI Server Module - A lightweight web UI for monitoring the News RSS Feed Processor

This module provides a Flask-based web server with Socket.IO for real-time log streaming.
It monitors log files and provides a web interface for viewing logs and system status.

The UI displays:
1. Real-time logs from the system
2. Status indicators for all services
3. API documentation for all available endpoints
4. An API testing tool for interacting with the API server
"""
import os
import json
import logging
import time
import threading
import queue
import random
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO
import requests

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
logger = logging.getLogger("ui")

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "news-man-secret-key"
socketio = SocketIO(app, cors_allowed_origins="*")

# Queue for storing log messages
log_queue = queue.Queue(maxsize=1000)

# Store recent logs
recent_logs = []
MAX_LOGS = 1000

# Create templates directory if it doesn't exist
os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)

# Create static directory if it doesn't exist
os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)

def log_system_events() -> None:
    """
    Log real system events and periodic status updates
    
    This function runs in a separate thread and periodically logs system events
    and status updates. It only logs real events, not simulated ones.
    """
    logger.info("Starting system event logging")
    
    # Add initial log about UI server starting
    startup_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_queue.put(f"{startup_time} - UI Server started")
    log_queue.put(f"{startup_time} - Monitoring real system logs")
    
    # Log system information
    try:
        import platform
        system_info = f"System: {platform.system()} {platform.release()} ({platform.machine()})"
        python_info = f"Python: {platform.python_version()}"
        log_queue.put(f"{startup_time} - {system_info}")
        log_queue.put(f"{startup_time} - {python_info}")
    except Exception as e:
        logger.error(f"Error getting system information: {e}")
    
    # Periodically log system status
    check_interval = 60  # seconds
    last_status_check = 0
    
    while True:
        try:
            current_time = time.time()
            
            # Check status every minute
            if current_time - last_status_check >= check_interval:
                # Get memory usage
                try:
                    import psutil
                    process = psutil.Process(os.getpid())
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / (1024 * 1024)
                    log_queue.put(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Memory usage: {memory_mb:.2f} MB")
                except ImportError:
                    # psutil not available, skip memory logging
                    pass
                except Exception as mem_error:
                    logger.error(f"Error getting memory usage: {mem_error}")
                
                last_status_check = current_time
            
            # Sleep for a short time to avoid high CPU usage
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in system event logger: {e}")
            time.sleep(10)  # Longer sleep on error

def tail_log_file(log_file_path: str) -> None:
    """
    Tail a log file and add lines to the log queue
    
    Args:
        log_file_path: Path to the log file to monitor
    """
    retry_count = 0
    max_retries = 10  # Increased retries
    retry_delay = 3  # Reduced delay for faster recovery
    
    # Add a direct log message to the file to test if it appears in UI
    try:
        with open(log_file_path, "a") as f:
            f.write(f"{datetime.now().isoformat()} - UI Server started monitoring logs\n")
    except Exception as e:
        logger.error(f"Could not write to log file: {e}")
    
    while retry_count < max_retries:
        try:
            # Check if log directory exists, create it if not
            log_dir = os.path.dirname(log_file_path)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
                logger.info(f"Created log directory: {log_dir}")
                # Add to queue for UI display
                log_queue.put(f"Created log directory: {log_dir}")
            
            # Check if log file exists, create it if not
            if not os.path.exists(log_file_path):
                with open(log_file_path, "w") as f:
                    startup_msg = f"Log file created at {datetime.now().isoformat()}\n"
                    f.write(startup_msg)
                logger.info(f"Created log file: {log_file_path}")
                # Add to queue for UI display
                log_queue.put(f"Created log file: {log_file_path}")
            
            # Use subprocess to tail the log file
            process = subprocess.Popen(
                ["tail", "-F", log_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1  # Line buffered
            )
            
            logger.info(f"Successfully started tailing log file: {log_file_path}")
            log_queue.put(f"UI Server is now monitoring log file: {log_file_path}")
            
            # Write a test message to the log file
            try:
                with open(log_file_path, "a") as f:
                    f.write(f"{datetime.now().isoformat()} - Log monitoring active\n")
            except Exception as write_err:
                logger.error(f"Could not write test message: {write_err}")
            
            # Read lines from the process output
            for line in process.stdout:
                if line.strip():  # Only process non-empty lines
                    # Add to queue
                    try:
                        log_queue.put(line.strip())
                    except queue.Full:
                        # If queue is full, remove oldest item
                        try:
                            log_queue.get_nowait()
                            log_queue.put(line.strip())
                        except queue.Empty:
                            pass
            
            # If we reach here, the process has ended unexpectedly
            logger.warning(f"Log tailing process ended unexpectedly for {log_file_path}")
            retry_count += 1
            time.sleep(retry_delay)
            
        except FileNotFoundError:
            logger.error(f"Log file not found: {log_file_path}")
            log_queue.put(f"Error: Log file not found: {log_file_path}. Retrying in {retry_delay} seconds...")
            retry_count += 1
            time.sleep(retry_delay)
            
        except PermissionError:
            logger.error(f"Permission denied when accessing log file: {log_file_path}")
            log_queue.put(f"Error: Permission denied when accessing log file: {log_file_path}. Retrying in {retry_delay} seconds...")
            retry_count += 1
            time.sleep(retry_delay)
            
        except Exception as e:
            logger.error(f"Error tailing log file: {e}")
            log_queue.put(f"Error monitoring log file: {str(e)}. Retrying in {retry_delay} seconds...")
            retry_count += 1
            time.sleep(retry_delay)
    
    # If we've exhausted retries, log a final error
    if retry_count >= max_retries:
        error_msg = f"Failed to monitor log file after {max_retries} attempts: {log_file_path}"
        logger.error(error_msg)
        log_queue.put(error_msg)

def process_logs() -> None:
    """
    Process logs from the queue and emit to clients
    
    This function runs in an infinite loop, pulling logs from the queue
    and emitting them to connected clients via Socket.IO. It also maintains
    a buffer of recent logs for new clients that connect.
    """
    consecutive_errors = 0
    max_consecutive_errors = 5
    error_cooldown = 0
    last_heartbeat = time.time()
    heartbeat_interval = 30  # seconds
    
    # Add initial log message
    log_queue.put("Log processor started - UI is now displaying logs")
    
    while True:
        try:
            # Periodic heartbeat to ensure logs are flowing
            current_time = time.time()
            if current_time - last_heartbeat > heartbeat_interval:
                log_queue.put(f"UI Log Heartbeat - {datetime.now().isoformat()}")
                last_heartbeat = current_time
            
            # If we've had too many consecutive errors, cool down
            if consecutive_errors >= max_consecutive_errors:
                if error_cooldown == 0:
                    logger.warning(f"Too many consecutive errors ({consecutive_errors}), cooling down for 30 seconds")
                    error_cooldown = 30
                    
                error_cooldown -= 1
                time.sleep(1)
                continue
                
            # Get log from queue with timeout
            try:
                log = log_queue.get(timeout=1)
                # Log that we received a message (to console only)
                logger.debug(f"Processing log: {log[:50]}..." if len(log) > 50 else f"Processing log: {log}")
            except queue.Empty:
                # No logs in queue, just wait a bit
                time.sleep(0.1)
                continue
                
            # Add timestamp if not present
            if not (log.startswith("20") and log[4:5] == "-"):  # Better check for ISO date format
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log = f"{timestamp} {log}"
            
            # Add to recent logs buffer with thread safety
            try:
                if len(recent_logs) >= MAX_LOGS:
                    recent_logs.pop(0)
                recent_logs.append(log)
            except Exception as buffer_error:
                logger.error(f"Error managing log buffer: {buffer_error}")
            
            # Emit to clients - this is what sends logs to the UI
            try:
                # Debug output to confirm emission
                logger.debug(f"Emitting log to clients: {log[:50]}..." if len(log) > 50 else f"Emitting log: {log}")
                socketio.emit("new_log", {"log": log})
                # Reset consecutive errors counter on success
                consecutive_errors = 0
            except Exception as emit_error:
                logger.error(f"Error emitting log to clients: {emit_error}")
                consecutive_errors += 1
                
        except Exception as e:
            error_msg = f"Unexpected error in log processor: {e}"
            logger.error(error_msg)
            consecutive_errors += 1
            time.sleep(1)

@app.route("/")
def index():
    """Render the main UI page"""
    return render_template("index.html")

@app.route("/api/logs")
def get_logs():
    """Get recent logs"""
    return jsonify({"logs": recent_logs})

@app.route("/api/status")
def get_status():
    """
    Get system status for all services
    
    Returns:
        JSON with status of all services (qdrant, processor, api, ui)
    """
    # Initialize status
    status = {
        "qdrant": False,
        "processor": False,
        "api": False,
        "ui": True  # UI is always running if this endpoint is called
    }
    
    # Check Qdrant status
    try:
        qdrant_response = requests.get("http://host.docker.internal:6333/collections", timeout=2)
        status["qdrant"] = qdrant_response.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to check Qdrant status: {e}")
    
    # Check API server status
    try:
        api_response = requests.get("http://host.docker.internal:8427/health", timeout=2)
        status["api"] = api_response.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to check API server status: {e}")
    
    # Check processor status (assume it's running if we can access the API)
    # In a real-world scenario, we would have a dedicated health check for the processor
    status["processor"] = status["api"]
    
    # Create status info response
    status_info = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "details": {
            "qdrant": "Connected" if status["qdrant"] else "Not connected",
            "processor": "Running" if status["processor"] else "Not running",
            "api": "Available" if status["api"] else "Not available",
            "ui": "Running"
        }
    }
    
    # Log the status
    services_status = ", ".join([f"{k}: {'✓' if v else '✗'}" for k, v in status.items()])
    log_queue.put(f"Status check: {services_status}")
    
    return jsonify(status_info)

@socketio.on("connect")
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")

@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")

def start_log_processor(log_file_path: str) -> None:
    """
    Start the log processor threads
    
    This function initializes and starts all the necessary threads for log processing:
    1. System event logger thread - logs system events and status
    2. Log file tailing thread - monitors the log file for new entries
    3. Log processing thread - processes logs from the queue and emits to clients
    
    Args:
        log_file_path: Path to the log file to monitor
    """
    threads = []
    
    try:
        # Add a startup message directly to the log file to ensure it has content
        try:
            with open(log_file_path, "a") as f:
                f.write(f"{datetime.now().isoformat()} - UI Server initializing log processor\n")
        except Exception as e:
            logger.error(f"Could not write startup message to log file: {e}")
        
        # Start system event logger thread
        logger.info("Starting system event logger thread")
        system_log_thread = threading.Thread(target=log_system_events, daemon=True, name="SystemEventLogger")
        system_log_thread.start()
        threads.append(system_log_thread)
        
        # Start log processing thread first so it can handle messages
        logger.info("Starting log processing thread")
        process_thread = threading.Thread(target=process_logs, daemon=True, name="LogProcessor")
        process_thread.start()
        threads.append(process_thread)
        
        # Give the log processor a moment to initialize
        time.sleep(0.5)
        
        # Set up log file monitoring - this is the primary source of real logs
        try:
            # Validate log file path
            if not log_file_path:
                raise ValueError("Log file path cannot be empty")
                
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
                logger.info(f"Created log directory: {log_dir}")
                log_queue.put(f"Created log directory: {log_dir}")
                
            # Create log file if it doesn't exist
            if not os.path.exists(log_file_path):
                with open(log_file_path, "w") as f:
                    f.write(f"{datetime.now().isoformat()} - Log file initialized\n")
                logger.info(f"Created log file: {log_file_path}")
                log_queue.put(f"Created log file: {log_file_path}")
            
            # Start log file tailing thread
            logger.info(f"Starting log file tailing thread for: {log_file_path}")
            log_thread = threading.Thread(target=tail_log_file, args=(log_file_path,), daemon=True, name="LogFileTailer")
            log_thread.start()
            threads.append(log_thread)
            
            # Add a direct message to the log queue
            log_queue.put(f"Monitoring log file: {log_file_path}")
            
        except Exception as e:
            logger.error(f"Error setting up log file monitoring: {e}")
            # Add error to log queue so it appears in the UI
            log_queue.put(f"Error setting up log file monitoring: {e}")
        
        # Log startup message
        startup_msg = "Log processor started - UI is now showing logs from all services"
        logger.info(startup_msg)
        log_queue.put(startup_msg)
        
        # Log active threads
        thread_names = [t.name for t in threads]
        logger.info(f"Active log processing threads: {', '.join(thread_names)}")
        log_queue.put(f"Active log processing threads: {', '.join(thread_names)}")
        
        # Add a test message to the log file
        try:
            with open(log_file_path, "a") as f:
                f.write(f"{datetime.now().isoformat()} - Log processor initialization complete\n")
        except Exception as e:
            logger.error(f"Could not write test message to log file: {e}")
        
    except Exception as e:
        logger.error(f"Error starting log processor: {e}")
        # Add error to log queue so it appears in the UI
        log_queue.put(f"Error starting log processor: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="News RSS Feed Processor Simple UI")
    parser.add_argument("--log-file", type=str, default="/tmp/news_man.log", help="Path to log file to monitor")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8428, help="Port to bind to")
    
    args = parser.parse_args()
    
    # Start log processor
    start_log_processor(args.log_file)
    
    # Start Flask server
    socketio.run(app, host=args.host, port=args.port, debug=True, allow_unsafe_werkzeug=True)
