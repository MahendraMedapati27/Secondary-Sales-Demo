# Azure App Service Startup Command Fix

## Current Issue:
Azure App Service is looking for `startup.py` but can't find it:
```
python: can't open file '/home/site/wwwroot/startup.py': [Errno 2] No such file or directory
```

## Solution Options:

### Option 1: Use run.py (Recommended)
Change the Azure App Service startup command to:
```
python run.py
```

### Option 2: Use gunicorn
Change the Azure App Service startup command to:
```
gunicorn --bind=0.0.0.0:8000 --workers=4 run:app
```

### Option 3: Use waitress directly
Change the Azure App Service startup command to:
```
python -c "from waitress import serve; from app import create_app; serve(create_app(), host='0.0.0.0', port=8000, threads=4)"
```

## How to Change Startup Command in Azure:

1. Go to Azure Portal
2. Navigate to your App Service
3. Go to Configuration > General settings
4. Change "Startup Command" to one of the options above
5. Save the configuration
6. Restart the App Service

## Recommended Fix:
Use **Option 1** (`python run.py`) as it's the simplest and most reliable.
