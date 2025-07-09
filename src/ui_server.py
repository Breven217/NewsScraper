"""
UI Server - A simple web UI for monitoring the News RSS Feed Processor
"""
import os
import json
import logging
import time
import threading
import queue
from datetime import datetime
from typing import Dict, List, Any, Optional
import subprocess
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from ansi2html import Ansi2HTMLConverter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ui_server")

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "news-man-secret-key"
socketio = SocketIO(app, cors_allowed_origins="*")

# Queue for storing log messages
log_queue = queue.Queue(maxsize=1000)

# Queue for storing request information
request_queue = queue.Queue(maxsize=100)

# Store recent logs and requests
recent_logs = []
recent_requests = []
MAX_LOGS = 1000
MAX_REQUESTS = 100

# ANSI to HTML converter for colorizing logs
ansi_converter = Ansi2HTMLConverter()

# Create templates directory if it doesn't exist
os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)

# Create static directory if it doesn't exist
os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)

class RequestTracker:
    """Track API requests and their status"""
    
    def __init__(self):
        self.requests = {}
        self.request_counter = 0
    
    def add_request(self, endpoint: str, method: str, params: Dict[str, Any]) -> int:
        """Add a new request to track"""
        request_id = self.request_counter
        self.request_counter += 1
        
        request_info = {
            "id": request_id,
            "endpoint": endpoint,
            "method": method,
            "params": params,
            "start_time": datetime.now().isoformat(),
            "status": "pending",
            "response": None,
            "duration_ms": 0
        }
        
        self.requests[request_id] = request_info
        
        # Add to queue for UI
        if len(recent_requests) >= MAX_REQUESTS:
            recent_requests.pop(0)
        recent_requests.append(request_info)
        
        # Emit to UI
        socketio.emit("new_request", request_info)
        
        return request_id
    
    def update_request(self, request_id: int, status: str, response: Optional[Any] = None) -> None:
        """Update the status of a request"""
        if request_id not in self.requests:
            return
        
        request_info = self.requests[request_id]
        request_info["status"] = status
        
        if response is not None:
            request_info["response"] = response
            
        # Calculate duration
        start_time = datetime.fromisoformat(request_info["start_time"])
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        request_info["duration_ms"] = round(duration_ms, 2)
        
        # Update in recent requests
        for i, req in enumerate(recent_requests):
            if req["id"] == request_id:
                recent_requests[i] = request_info
                break
        
        # Emit to UI
        socketio.emit("update_request", request_info)

# Initialize request tracker
request_tracker = RequestTracker()

def tail_log_file(log_file_path: str) -> None:
    """Tail a log file and add lines to the log queue"""
    try:
        # Check if log file exists, create it if not
        if not os.path.exists(log_file_path):
            with open(log_file_path, "w") as f:
                f.write(f"Log file created at {datetime.now().isoformat()}\n")
        
        # Use subprocess to tail the log file
        process = subprocess.Popen(
            ["tail", "-F", log_file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Read lines from the process output
        for line in process.stdout:
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
    except Exception as e:
        logger.error(f"Error tailing log file: {e}")

def process_logs() -> None:
    """Process logs from the queue and emit to clients"""
    while True:
        try:
            # Get log from queue
            log = log_queue.get(timeout=1)
            
            # Convert ANSI colors to HTML
            html_log = ansi_converter.convert(log, full=False)
            
            # Add timestamp if not present
            if not log.startswith("20"):  # Simple check for ISO date format
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                html_log = f"<span class='timestamp'>{timestamp}</span> {html_log}"
            
            # Add to recent logs
            if len(recent_logs) >= MAX_LOGS:
                recent_logs.pop(0)
            recent_logs.append(html_log)
            
            # Emit to clients
            socketio.emit("new_log", {"log": html_log})
            
        except queue.Empty:
            # No logs in queue, sleep briefly
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error processing logs: {e}")
            time.sleep(1)

@app.route("/")
def index():
    """Render the main UI page"""
    return render_template("index.html")

@app.route("/api/logs")
def get_logs():
    """Get recent logs"""
    return jsonify({"logs": recent_logs})

@app.route("/api/requests")
def get_requests():
    """Get recent requests"""
    return jsonify({"requests": recent_requests})

@app.route("/api/status")
def get_status():
    """Get system status"""
    # Check if services are running
    qdrant_running = False
    processor_running = False
    
    try:
        # Check Qdrant
        import requests
        response = requests.get("http://localhost:6333/health", timeout=2)
        qdrant_running = response.status_code == 200
    except Exception:
        pass
    
    try:
        # Check if processor is running
        processor_running = subprocess.call(
            ["pgrep", "-f", "docker_entrypoint.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ) == 0
    except Exception:
        pass
    
    return jsonify({
        "status": {
            "qdrant": qdrant_running,
            "processor": processor_running,
            "ui": True
        },
        "timestamp": datetime.now().isoformat()
    })

@socketio.on("connect")
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")

@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")

def start_log_processor(log_file_path: str) -> None:
    """Start the log processor thread"""
    log_thread = threading.Thread(target=tail_log_file, args=(log_file_path,), daemon=True)
    log_thread.start()
    
    process_thread = threading.Thread(target=process_logs, daemon=True)
    process_thread.start()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="News RSS Feed Processor UI")
    parser.add_argument("--log-file", type=str, default="/tmp/news_man.log", help="Path to log file to monitor")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8428, help="Port to bind to")
    
    args = parser.parse_args()
    
    # Start log processor
    start_log_processor(args.log_file)
    
    # Start Flask server
    socketio.run(app, host=args.host, port=args.port, debug=True, allow_unsafe_werkzeug=True)
