#!/bin/bash
# UNCaGED Production Start Script

set -e

# Navigate to script directory
cd "$(dirname "$0")"

# Load .env if present
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

export PORT=${PORT:-5000}

if [ -z "${SECRET_KEY:-}" ] || [ "${SECRET_KEY}" = "yoursecretkeyhere" ]; then
    echo "ERROR: Set a strong SECRET_KEY in .env before starting production."
    exit 1
fi

if [ -z "${DASHBOARD_USER:-}" ] || [ -z "${DASHBOARD_PASS:-}" ]; then
    echo "ERROR: Set DASHBOARD_USER and DASHBOARD_PASS in .env before starting production."
    exit 1
fi

if [ "${DASHBOARD_USER}" = "admin" ] && [ "${DASHBOARD_PASS}" = "admin" ]; then
    echo "ERROR: Default admin/admin credentials are not allowed for external access."
    exit 1
fi

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
python3 server.py
