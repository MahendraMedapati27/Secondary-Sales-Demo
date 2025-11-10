#!/bin/bash

echo "===================================="
echo "🚀 Quantum Blue AI Chatbot Starting"
echo "===================================="

# Start the application with Gunicorn
# Database initialization happens in application.py
echo "Starting Gunicorn WSGI server..."
gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers=4 --threads=2 application:app

