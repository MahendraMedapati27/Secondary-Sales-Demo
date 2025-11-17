# PowerShell script to get Microsoft Graph credentials
# Run this script to retrieve the client secret and configure permissions

Write-Host "=== Microsoft Graph API Configuration ===" -ForegroundColor Cyan
Write-Host ""

# Display current values
Write-Host "Current Configuration:" -ForegroundColor Yellow
Write-Host "Tenant ID: 54904ca2-e5a0-481c-a10a-73242e6476ea"
Write-Host "Client ID: bd9e0718-8df4-48b9-9cfd-2293ac6020f5"
Write-Host "Sender Email: mahendra@highvolt.tech"
Write-Host ""

# Check if Azure CLI is available
try {
    $azVersion = az --version 2>&1
    Write-Host "Azure CLI is installed" -ForegroundColor Green
} catch {
    Write-Host "Azure CLI is not installed. Please install it first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Step 1: Get Client Secret ===" -ForegroundColor Cyan
Write-Host "To get the client secret, you have two options:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Option A - Azure Portal (Recommended):" -ForegroundColor Green
Write-Host "1. Go to: https://portal.azure.com"
Write-Host "2. Navigate to: Azure Active Directory > App registrations"
Write-Host "3. Find app: HVChatbot-SP (bd9e0718-8df4-48b9-9cfd-2293ac6020f5)"
Write-Host "4. Go to: Certificates & secrets"
Write-Host "5. Click 'New client secret'"
Write-Host "6. Copy the secret VALUE (you can only see it once!)"
Write-Host "7. Update .env file: MS_GRAPH_CLIENT_SECRET=<your-secret>"
Write-Host ""

Write-Host "Option B - Azure CLI (if you have permissions):" -ForegroundColor Green
Write-Host "Run: az ad app credential reset --id bd9e0718-8df4-48b9-9cfd-2293ac6020f5 --append --display-name 'Chatbot Email Service' --years 2"
Write-Host ""

Write-Host "=== Step 2: Add Mail.Send Permission ===" -ForegroundColor Cyan
Write-Host "The app needs 'Mail.Send' permission to send emails." -ForegroundColor Yellow
Write-Host ""
Write-Host "Via Azure Portal:" -ForegroundColor Green
Write-Host "1. Go to: Azure Active Directory > App registrations > HVChatbot-SP"
Write-Host "2. Click: API permissions"
Write-Host "3. Click: Add a permission"
Write-Host "4. Select: Microsoft Graph"
Write-Host "5. Select: Application permissions"
Write-Host "6. Search for: Mail.Send"
Write-Host "7. Check: Mail.Send"
Write-Host "8. Click: Add permissions"
Write-Host "9. Click: Grant admin consent for [Your Organization]"
Write-Host ""

Write-Host "Via Azure CLI (if you have admin permissions):" -ForegroundColor Green
Write-Host "Run: az ad app permission add --id bd9e0718-8df4-48b9-9cfd-2293ac6020f5 --api 00000003-0000-0000-c000-000000000000 --api-permissions e5330c85-8e83-49d0-a0b0-6bdf8b7c8b3e=Role"
Write-Host "Run: az ad app permission admin-consent --id bd9e0718-8df4-48b9-9cfd-2293ac6020f5"
Write-Host ""

Write-Host "=== Step 3: Verify Configuration ===" -ForegroundColor Cyan
Write-Host "After completing the steps above, verify your .env file contains:" -ForegroundColor Yellow
Write-Host "MS_GRAPH_TENANT_ID=54904ca2-e5a0-481c-a10a-73242e6476ea"
Write-Host "MS_GRAPH_CLIENT_ID=bd9e0718-8df4-48b9-9cfd-2293ac6020f5"
Write-Host "MS_GRAPH_CLIENT_SECRET=<your-secret-here>"
Write-Host "MS_GRAPH_SENDER_EMAIL=mahendra@highvolt.tech"
Write-Host ""

Write-Host "=== Current App Permissions ===" -ForegroundColor Cyan
az ad app permission list --id bd9e0718-8df4-48b9-9cfd-2293ac6020f5 --query "[].{resourceAppId:resourceAppId, permissions:resourceAccess[].{id:id, type:type}}" -o table

Write-Host ""
Write-Host "=== Current Client Secrets ===" -ForegroundColor Cyan
az ad app credential list --id bd9e0718-8df4-48b9-9cfd-2293ac6020f5 --query "[].{keyId:keyId, hint:hint, startDate:startDateTime, endDate:endDateTime}" -o table

Write-Host ""
Write-Host "Note: Client secret values cannot be retrieved after creation for security reasons." -ForegroundColor Yellow
Write-Host "You must create a new secret if you don't have the existing one." -ForegroundColor Yellow

