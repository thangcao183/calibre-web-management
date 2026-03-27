#!/bin/bash
cd "$(dirname "$0")"

echo "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing requirements..."
pip install -r requirements.txt
playwright install chromium

echo "Starting UNCaGED Web Dashboard..."
python3 server.py
