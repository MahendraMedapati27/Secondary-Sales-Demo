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
        # Import the main function from run.py and execute it
        from run import main
        
        print("Starting Flask application via run.py...")
        main()
        
    except ImportError as e:
        print(f"Error importing run.py: {e}")
        print("Make sure run.py exists and contains a main function")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)
