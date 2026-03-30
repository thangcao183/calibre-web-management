import os
import logging
from dotenv import load_dotenv
from waitress import serve
from libs.kobo_device import start_tcp_listener
from libs.watcher import start_watcher

# Load environment variables from .env file
load_dotenv()

from server import app

# Basic logging configuration for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("waitress")

if __name__ == "__main__":
    print("-" * 50)
    print("🚀 UNCaGED Dashboard starting in PRODUCTION mode...")
    
    # Start background threads (TCP listener for Kobo and File Watcher)
    logger.info("Starting background tasks...")
    start_tcp_listener()
    start_watcher()
    
    port = int(os.getenv("PORT", 5000))
    print(f"🌍 Serving on http://0.0.0.0:{port}")
    print("-" * 50)
    
    # Run using Waitress (Multi-threaded production WSGI server)
    serve(app, host='0.0.0.0', port=port, threads=6)
