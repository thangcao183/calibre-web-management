#!/bin/bash
# UNCaGED Production Start Script

# Navigate to script directory
cd "$(dirname "$0")"

# Local configuration fallback
export DASHBOARD_USER=${DASHBOARD_USER:-admin}
export DASHBOARD_PASS=${DASHBOARD_PASS:-admin}
export PORT=${PORT:-5000}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
    ./venv/bin/playwright install chromium
fi

# Activate venv
source venv/bin/activate

echo "Starting Dashboard Service..."
# Use the production server script
python3 server_prod.py
