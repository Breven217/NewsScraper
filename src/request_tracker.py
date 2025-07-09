"""
Request Tracker - Middleware for tracking API requests
"""
import json
import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Get log file path from environment variable or use default
LOG_FILE = os.getenv("LOG_FILE", "/var/log/news_man/news_man.log")

# Configure logging
logger = logging.getLogger("request_tracker")

# Store recent requests
recent_requests = []
MAX_REQUESTS = 100
request_counter = 0

class RequestTrackerMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking API requests"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        global request_counter
        request_id = request_counter
        request_counter += 1
        
        # Get request details
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        
        # Log request start
        start_time = time.time()
        logger.info(f"REQUEST #{request_id} START: {method} {path} {json.dumps(query_params)}")
        
        # Create request info
        request_info = {
            "id": request_id,
            "endpoint": path,
            "method": method,
            "params": query_params,
            "start_time": datetime.now().isoformat(),
            "status": "pending",
            "response": None,
            "duration_ms": 0
        }
        
        # Add to recent requests
        if len(recent_requests) >= MAX_REQUESTS:
            recent_requests.pop(0)
        recent_requests.append(request_info)
        
        # Process the request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Update request info
            request_info["status"] = "success" if response.status_code < 400 else "error"
            request_info["duration_ms"] = duration_ms
            
            # Try to get response body
            response_body = b""
            try:
                # Save original response body
                response_body = await response.body()
                # Create new response with the same body
                new_response = Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
                
                # Try to parse JSON response
                try:
                    if response.headers.get("content-type") == "application/json":
                        request_info["response"] = json.loads(response_body)
                    else:
                        request_info["response"] = {"content_type": response.headers.get("content-type"), "size": len(response_body)}
                except:
                    request_info["response"] = {"error": "Could not parse response"}
                
                # Log request completion
                logger.info(f"REQUEST #{request_id} COMPLETE: {method} {path} - {response.status_code} - {duration_ms}ms")
                
                return new_response
            except Exception as e:
                logger.error(f"Error processing response: {e}")
                return response
            
        except Exception as e:
            # Update request info for error
            duration_ms = round((time.time() - start_time) * 1000, 2)
            request_info["status"] = "error"
            request_info["duration_ms"] = duration_ms
            request_info["response"] = {"error": str(e)}
            
            # Log error
            logger.error(f"REQUEST #{request_id} ERROR: {method} {path} - {str(e)}")
            raise e

def get_recent_requests() -> List[Dict[str, Any]]:
    """Get recent requests"""
    return recent_requests
