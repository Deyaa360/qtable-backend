# Gunicorn configuration for WebSocket compatibility
# Single worker required for maintaining WebSocket connections

import os

# Force single worker for WebSocket connections
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"

# Bind to Railway's port
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Connection settings optimized for WebSocket
worker_connections = 1000
keepalive = 30

# Timeout settings for long-running WebSocket connections
timeout = 120
graceful_timeout = 30

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"

# Prevent workers from being recycled
max_requests = 0
max_requests_jitter = 0

print(f"🔧 Gunicorn config: {workers} worker(s) on {bind}")
