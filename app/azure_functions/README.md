# Dealer Stock CSV Processor - Azure Function

This Azure Function automatically processes CSV files uploaded to Azure Blob Storage and imports dealer-wise stock details into the database.

## Overview

**Function Type**: Event Grid Trigger  
**Event Type**: `Microsoft.Storage.BlobCreated`  
**Trigger Path**: `gold/Dealer Wise Stock Details/Dealer_Wise_Stock.csv/`  
**Storage Account**: `pipelinestorage4196`  
**Container**: `gold`  
**Current Mode**: 🚀 **PRODUCTION MODE** - Imports all rows from CSV files

## Architecture

```
Azure Blob Storage (gold container)
    └── Dealer Wise Stock Details/
        └── Dealer_Wise_Stock.csv/
            └── [CSV files uploaded here]
                    ↓
            Event Grid notification
                    ↓
        Azure Function triggered
                    ↓
        1. Download CSV file
        2. Extract stock details
        3. Import to SQL Database
```

## Features

- **Event-Driven**: Uses Event Grid for instant triggering (more reliable than polling)
- **CSV Processing**: Extracts dealer-wise stock details from CSV files
- **Database Integration**: Automatically imports data to SQL Server database
- **Intelligent File Tracking**: Only processes new files, prevents duplicate processing
- **Error Handling**: Comprehensive logging and error tracking
- **Duplicate Prevention**: Checks for existing records before importing
- **Processing History**: Track all processed files with statistics
- **Management APIs**: Query processing history and check file status

## Prerequisites

1. **Azure Account** with appropriate permissions
2. **Azure Storage Account** (`pipelinestorage4196`)
3. **Azure SQL Database** with the chatbot database schema
4. **Azure Function App** (Python 3.10 or higher)
5. **Event Grid** subscription configured for the storage account

## Configuration

### 1. Local Development Setup

Create a `local.settings.json` file:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=pipelinestorage4196;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "SQL_SERVER": "your-server.database.windows.net",
    "SQL_DATABASE": "your-database-name",
    "SQL_USERNAME": "your-username",
    "SQL_PASSWORD": "your-password"
  }
}
```

### 2. Azure Configuration

Set the following Application Settings in your Azure Function App:

| Setting Name | Description | Example |
|-------------|-------------|---------|
| `AzureWebJobsStorage` | Storage account connection string | `DefaultEndpointsProtocol=https;...` |
| `SQL_SERVER` | SQL Server hostname | `your-server.database.windows.net` |
| `SQL_DATABASE` | Database name | `chatbot_db` |
| `SQL_USERNAME` | Database username | `sqladmin` |
| `SQL_PASSWORD` | Database password | `YourSecurePassword123!` |

## File Structure

```
azure_functions/
├── function_app.py              # Main function code
├── excel_extractor.py           # CSV extraction logic
├── stock_importer.py            # Database import logic
├── database_connection.py       # Database connectivity
├── requirements.txt             # Python dependencies
├── host.json                    # Function host configuration
├── local.settings.json          # Local development settings (not in git)
├── .funcignore                  # Files to ignore during deployment
└── README.md                    # This file
```

## Deployment

### Option 1: Deploy from VS Code

1. Install the **Azure Functions** extension for VS Code
2. Open the `azure_functions` folder in VS Code
3. Click on the Azure icon in the sidebar
4. Sign in to your Azure account
5. Right-click on your Function App → Deploy to Function App
6. Select the `azure_functions` folder

### Option 2: Deploy using Azure CLI

```bash
# Login to Azure
az login

# Navigate to the function directory
cd app/azure_functions

# Deploy to Azure Function App
az functionapp deployment source config-zip \
  --resource-group YOUR_RESOURCE_GROUP \
  --name YOUR_FUNCTION_APP_NAME \
  --src deployment.zip
```

### Option 3: Deploy using Azure Functions Core Tools

```bash
# Install Azure Functions Core Tools (if not already installed)
# Windows: Install from https://docs.microsoft.com/azure/azure-functions/functions-run-local
# macOS: brew install azure-functions-core-tools@4
# Linux: Download from Microsoft

# Navigate to function directory
cd app/azure_functions

# Deploy
func azure functionapp publish YOUR_FUNCTION_APP_NAME
```

## Event Grid Setup

### Important: Configure Event Grid Subscription

After deploying the function, you need to create an Event Grid subscription:

1. **Go to Azure Portal** → Your Storage Account (`pipelinestorage4196`)
2. **Navigate to**: Events → Event Subscriptions
3. **Click**: + Event Subscription
4. **Configure**:
   - **Name**: `dealer-stock-csv-events`
   - **Event Schema**: Event Grid Schema
   - **Topic Type**: Storage Accounts (blob & GPv2)
   - **System Topic Name**: `pipelinestorage4196-events`
   - **Filter to Event Types**: 
     - ✅ Blob Created
   - **Endpoint Type**: Azure Function
   - **Endpoint**: Select your Function App → `dealer_stock_csv_processor`
   - **Filters** (Advanced):
     - **Subject Begins With**: `/blobServices/default/containers/gold/blobs/Dealer Wise Stock Details/Dealer_Wise_Stock.csv/`
     - **Subject Ends With**: `.csv`
5. **Click**: Create

## Testing

### Local Testing

1. **Start the function locally**:
   ```bash
   cd app/azure_functions
   func start
   ```

2. **Upload a CSV file** to:
   ```
   Container: gold
   Path: Dealer Wise Stock Details/Dealer_Wise_Stock.csv/test-file.csv
   ```

3. **Monitor logs** in the terminal

### Azure Testing

1. **Upload a CSV file** to the blob storage path
2. **Monitor execution**:
   - Azure Portal → Your Function App → Functions → `dealer_stock_csv_processor`
   - Click on "Monitor" tab to view executions
   - Check logs in "Logs" section

### Health Check

Test the health endpoint:
```bash
curl https://YOUR_FUNCTION_APP.azurewebsites.net/api/health
```

Expected response:
```json
{"status": "healthy", "service": "dealer-stock-csv-processor"}
```

### Check Processing History

View recently processed files:
```bash
curl https://YOUR_FUNCTION_APP.azurewebsites.net/api/processing-history?limit=50
```

Check if specific file was processed:
```bash
curl "https://YOUR_FUNCTION_APP.azurewebsites.net/api/check-file?file_name=myfile.csv"
```

See `FILE_TRACKING.md` for complete API documentation.

## CSV File Format

The function expects CSV files with the following columns (case-insensitive):

### Required Columns:
- `dealer` or `dealer_name` - Dealer/Distributor name
- `product_code` - Product code/ID
- `quantity` or `qty` - Quantity dispatched

### Optional Columns:
- `dealer_id` or `dealer_unique_id` - Dealer unique identifier
- `product_name` - Product name
- `dispatch_date` - Date of dispatch
- `lot_number` or `batch` - Lot/Batch number
- `expiry_date` - Product expiry date
- `sales_price` or `price` - Sales price per unit
- `invoice_id` or `invoice_number` - Invoice reference

### Example CSV:

```csv
Dealer Name,Dealer ID,Product Code,Product Name,Quantity,Dispatch Date,Sales Price
ABC Pharmacy,DIST_001,PROD123,Paracetamol 500mg,100,2024-01-15,10.50
XYZ Medical,DIST_002,PROD456,Amoxicillin 250mg,50,2024-01-15,25.00
```

## Monitoring and Logging

### View Logs in Azure Portal

1. Go to your Function App in Azure Portal
2. Navigate to: Functions → `dealer_stock_csv_processor` → Monitor
3. View recent invocations and logs

### Application Insights (Recommended)

Enable Application Insights for advanced monitoring:

1. Go to your Function App → Settings → Application Insights
2. Enable Application Insights
3. View detailed telemetry, performance metrics, and errors

### Log Messages

The function logs key events:

- ✅ `Successfully read X bytes from blob` - File downloaded
- 🔍 `Extracted X stock detail records` - Data extraction complete
- 💾 `Imported: X, Skipped: Y, Errors: Z` - Import results
- ❌ Error messages with stack traces

## Troubleshooting

### Function Not Triggering

**Issue**: CSV uploaded but function doesn't run

**Solutions**:
1. Check Event Grid subscription is correctly configured
2. Verify the blob path matches exactly: `gold/Dealer Wise Stock Details/Dealer_Wise_Stock.csv/`
3. Check Function App logs for errors
4. Ensure `AzureWebJobsStorage` connection string is correct

### Database Connection Errors

**Issue**: "Database connection failed"

**Solutions**:
1. Verify SQL Server firewall allows Azure services
2. Check database credentials in Application Settings
3. Test connection string using SQL Server Management Studio
4. Ensure database exists and has correct schema

### Import Errors

**Issue**: Records not imported

**Solutions**:
1. Check CSV file format matches expected columns
2. Verify dealers exist in the `users` table with role='distributor'
3. Review function logs for specific error messages
4. Check for duplicate records (function skips duplicates)

### "Dealer not found" Warnings

**Issue**: Stock not imported for some dealers

**Solutions**:
1. Ensure dealer exists in `users` table
2. Check dealer name matches exactly (case-insensitive)
3. Verify dealer has role='distributor'
4. Check `dealer_unique_id` if provided in CSV

## Performance Considerations

- **Batch Size**: Function processes entire CSV file in one execution
- **Large Files**: For files > 10MB, consider increasing function timeout
- **Concurrent Uploads**: Multiple files uploaded simultaneously will trigger separate function instances
- **Database Load**: Uses connection pooling to optimize database connections

## Security

- **Connection Strings**: Store in Azure Key Vault (recommended) or Application Settings
- **Managed Identity**: Use Managed Identity for database access (recommended)
- **Network Security**: Configure VNet integration if needed
- **Access Control**: Use Azure RBAC to control who can upload files

## Cost Optimization

- **Event Grid**: Pay-per-event pricing (~$0.60 per million events)
- **Function Execution**: Consumption plan bills per execution + execution time
- **Storage**: Blob storage standard rates apply
- **Estimated Cost**: ~$5-10/month for typical usage (100 files/day)

## Maintenance

### Update Function Code

1. Make changes to Python files
2. Test locally using `func start`
3. Deploy using any deployment method above
4. Monitor first few executions to ensure changes work

### Update Dependencies

1. Modify `requirements.txt`
2. Test locally
3. Redeploy function
4. Azure will automatically install new dependencies

## Support

For issues or questions:
1. Check Azure Function logs
2. Review Application Insights telemetry
3. Check Azure Service Health for platform issues
4. Contact your development team

## Related Documentation

- [Azure Functions Python Developer Guide](https://docs.microsoft.com/azure/azure-functions/functions-reference-python)
- [Azure Event Grid Documentation](https://docs.microsoft.com/azure/event-grid/)
- [Azure Blob Storage Documentation](https://docs.microsoft.com/azure/storage/blobs/)
