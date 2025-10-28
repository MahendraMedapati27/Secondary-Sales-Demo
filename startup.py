#!/usr/bin/env python3
"""
Azure App Service startup script
This file redirects to run.py for backward compatibility
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main application
if __name__ == "__main__":
    try:
        # Import the main application from run.py
        from run import app
        
        # Get the port from environment variable or use default
        port = int(os.environ.get('PORT', 8000))
        host = os.environ.get('HOST', '0.0.0.0')
        
        print(f"Starting Flask application on {host}:{port}")
        app.run(host=host, port=port, debug=False)
        
    except ImportError as e:
        print(f"Error importing run.py: {e}")
        print("Make sure run.py exists and contains a Flask app")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)
