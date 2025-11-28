"""
Microsoft Graph API Service for OneDrive/SharePoint Access
"""

import logging
import requests
import os
from typing import List, Dict, Optional, BinaryIO
from datetime import datetime

# Single logger initialization - logging.basicConfig should only be called once in __init__.py
logger = logging.getLogger(__name__)


class MicrosoftGraphService:
    """Service for interacting with Microsoft Graph API to access OneDrive/SharePoint"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        """
        Initialize Microsoft Graph Service
        
        Args:
            tenant_id: Azure AD tenant ID
            client_id: Azure AD application (client) ID
            client_secret: Azure AD application client secret
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        self._access_token = None
        self._token_expires_at = None
        
    def get_access_token(self) -> Optional[str]:
        """
        Get access token for Microsoft Graph API using client credentials flow
        
        Returns:
            Access token string or None if failed
        """
        try:
            # Check if token is still valid (with 5 minute buffer)
            if self._access_token and self._token_expires_at:
                if datetime.utcnow() < self._token_expires_at:
                    return self._access_token
            
            # Request new token
            token_data = {
                'client_id': self.client_id,
                'scope': 'https://graph.microsoft.com/.default',
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials'
            }
            
            response = requests.post(self.token_url, data=token_data, timeout=30)
            response.raise_for_status()
            
            token_json = response.json()
            self._access_token = token_json.get('access_token')
            expires_in = token_json.get('expires_in', 3600)  # Default to 1 hour
            
            # Calculate expiration time (with 5 minute buffer)
            from datetime import timedelta
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 300)
            
            if self._access_token:
                logger.info("Successfully obtained Microsoft Graph access token")
                return self._access_token
            else:
                logger.error("No access token in Microsoft Graph response")
                return None
                
        except Exception as e:
            logger.error(f"Error getting Microsoft Graph token: {str(e)}")
            return None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Graph API requests"""
        token = self.get_access_token()
        if not token:
            raise Exception("Failed to obtain access token")
        
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def get_site_id(self, site_url: str) -> Optional[str]:
        """
        Get SharePoint site ID from site URL
        
        Args:
            site_url: SharePoint site URL (e.g., https://highvolttech.sharepoint.com/sites/ITTeam)
            
        Returns:
            Site ID or None if failed
        """
        try:
            # Extract site path from URL
            # URL format: https://{tenant}.sharepoint.com/sites/{siteName}
            url_parts = site_url.replace('https://', '').split('/')
            if len(url_parts) < 3:
                logger.error(f"Invalid site URL format: {site_url}")
                return None
            
            tenant = url_parts[0]
            site_path = '/'.join(url_parts[1:])
            
            # Get site by path
            graph_url = f"{self.graph_base_url}/sites/{tenant}:/{site_path}"
            
            response = requests.get(graph_url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            
            site_data = response.json()
            site_id = site_data.get('id')
            
            if site_id:
                logger.info(f"Successfully retrieved site ID: {site_id}")
                return site_id
            else:
                logger.error("No site ID in response")
                return None
                
        except Exception as e:
            logger.error(f"Error getting site ID: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Graph API error details: {error_detail}")
                except:
                    logger.error(f"Graph API error response: {e.response.text}")
            return None
    
    def list_files_in_folder(self, site_id: str, folder_path: str) -> List[Dict]:
        """
        List files in a SharePoint folder
        
        Args:
            site_id: SharePoint site ID
            folder_path: Path to folder (e.g., /Shared Documents/IT/Order_Management_Chatbot)
            
        Returns:
            List of file metadata dictionaries
        """
        try:
            # Normalize folder path (remove leading/trailing slashes, ensure proper format)
            folder_path = folder_path.strip().strip('/')
            if not folder_path.startswith('/'):
                folder_path = '/' + folder_path
            
            # Get drive (document library) for the site
            drives_url = f"{self.graph_base_url}/sites/{site_id}/drives"
            response = requests.get(drives_url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            
            drives_data = response.json()
            drives = drives_data.get('value', [])
            
            if not drives:
                logger.error("No drives found for site")
                return []
            
            # Use the first drive (usually "Documents")
            drive_id = drives[0].get('id')
            
            # Get folder by path - SharePoint API path format
            # Try different path formats
            from urllib.parse import quote
            
            # Normalize path - remove leading slash and handle "Shared Documents"
            normalized_path = folder_path.strip().lstrip('/')
            
            # Try different path formats
            path_formats = [
                normalized_path,  # /Shared Documents/IT/Order_Management_Chatbot
                normalized_path.replace('/Shared Documents/', ''),  # IT/Order_Management_Chatbot
                f"/{normalized_path}",  # /Shared Documents/IT/Order_Management_Chatbot (with leading slash)
            ]
            
            folder_id = None
            for path_format in path_formats:
                try:
                    encoded_path = quote(path_format, safe='/')
                    folder_url = f"{self.graph_base_url}/sites/{site_id}/drives/{drive_id}/root:{encoded_path}"
                    response = requests.get(folder_url, headers=self._get_headers(), timeout=30)
                    response.raise_for_status()
                    folder_data = response.json()
                    folder_id = folder_data.get('id')
                    if folder_id:
                        logger.info(f"Successfully found folder using path: {path_format}")
                        break
                except requests.exceptions.HTTPError:
                    continue
            
            if not folder_id:
                # Try accessing via children of root - navigate through folder hierarchy
                try:
                    logger.info("Attempting to navigate folder hierarchy...")
                    root_url = f"{self.graph_base_url}/sites/{site_id}/drives/{drive_id}/root/children"
                    response = requests.get(root_url, headers=self._get_headers(), timeout=30)
                    response.raise_for_status()
                    root_items = response.json().get('value', [])
                    
                    logger.info(f"Root folder contains {len(root_items)} items")
                    for item in root_items[:10]:  # Log first 10 items
                        item_type = "folder" if item.get('folder') else "file"
                        logger.info(f"  - {item.get('name')} ({item_type})")
                    
                    # First, try to find IT folder directly in root (it might not be in Shared Documents)
                    it_folder_id = None
                    for item in root_items:
                        if item.get('name', '').upper() == 'IT' and item.get('folder'):
                            it_folder_id = item.get('id')
                            logger.info(f"Found 'IT' folder directly in root")
                            break
                    
                    # If IT not found in root, look in Shared Documents
                    if not it_folder_id:
                        # Find "Shared Documents" or "Documents" folder
                        shared_docs_id = None
                        for item in root_items:
                            item_name = item.get('name', '').lower()
                            if 'shared' in item_name and 'document' in item_name:
                                shared_docs_id = item.get('id')
                                logger.info(f"Found 'Shared Documents' folder: {item.get('name')}")
                                break
                            elif item_name == 'documents':
                                shared_docs_id = item.get('id')
                                logger.info(f"Found 'Documents' folder: {item.get('name')}")
                                break
                        
                        if shared_docs_id:
                            # Get children of Shared Documents
                            shared_docs_url = f"{self.graph_base_url}/sites/{site_id}/drives/{drive_id}/items/{shared_docs_id}/children"
                            response = requests.get(shared_docs_url, headers=self._get_headers(), timeout=30)
                            response.raise_for_status()
                            shared_items = response.json().get('value', [])
                            
                            logger.info(f"Shared Documents contains {len(shared_items)} items")
                            for item in shared_items[:5]:
                                logger.info(f"  - {item.get('name')}")
                            
                            # Find IT folder in Shared Documents
                            for shared_item in shared_items:
                                if shared_item.get('name', '').upper() == 'IT' and shared_item.get('folder'):
                                    it_folder_id = shared_item.get('id')
                                    logger.info(f"Found 'IT' folder in Shared Documents")
                                    break
                    
                    if it_folder_id:
                        # Get children of IT folder
                        it_url = f"{self.graph_base_url}/sites/{site_id}/drives/{drive_id}/items/{it_folder_id}/children"
                        response = requests.get(it_url, headers=self._get_headers(), timeout=30)
                        response.raise_for_status()
                        it_items = response.json().get('value', [])
                        
                        logger.info(f"IT folder contains {len(it_items)} items")
                        for item in it_items:
                            logger.info(f"  - {item.get('name')}")
                        
                        # Find Order_Management_Chatbot folder (case-insensitive, partial match)
                        for it_item in it_items:
                            item_name = it_item.get('name', '').lower()
                            if 'order' in item_name and 'management' in item_name and 'chatbot' in item_name:
                                folder_id = it_item.get('id')
                                logger.info(f"Found target folder: {it_item.get('name')}")
                                break
                            elif 'order' in item_name and 'management' in item_name:
                                folder_id = it_item.get('id')
                                logger.info(f"Found target folder: {it_item.get('name')}")
                                break
                            elif 'order' in item_name and 'chatbot' in item_name:
                                folder_id = it_item.get('id')
                                logger.info(f"Found target folder: {it_item.get('name')}")
                                break
                except Exception as nav_e:
                    logger.error(f"Error navigating folders: {str(nav_e)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            if not folder_id:
                logger.error("Could not find folder with any method")
                logger.error("Please verify the folder path exists in SharePoint")
                return []
            
            # List children (files) in folder
            children_url = f"{self.graph_base_url}/sites/{site_id}/drives/{drive_id}/items/{folder_id}/children"
            response = requests.get(children_url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            
            children_data = response.json()
            files = children_data.get('value', [])
            
            # Filter for Excel and CSV files
            data_files = [
                {
                    'id': file.get('id'),
                    'name': file.get('name'),
                    'webUrl': file.get('webUrl'),
                    'lastModifiedDateTime': file.get('lastModifiedDateTime'),
                    'size': file.get('size'),
                    'createdDateTime': file.get('createdDateTime')
                }
                for file in files
                if file.get('name', '').lower().endswith(('.xlsx', '.xls', '.csv'))
            ]
            
            logger.info(f"Found {len(data_files)} data files (Excel/CSV) in folder")
            return data_files
            
        except Exception as e:
            logger.error(f"Error listing files in folder: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Graph API error details: {error_detail}")
                except:
                    logger.error(f"Graph API error response: {e.response.text}")
            return []
    
    def download_file(self, site_id: str, file_id: str) -> Optional[bytes]:
        """
        Download file content from SharePoint
        
        Args:
            site_id: SharePoint site ID
            file_id: File ID
            
        Returns:
            File content as bytes or None if failed
        """
        try:
            # Get drive ID first
            drives_url = f"{self.graph_base_url}/sites/{site_id}/drives"
            response = requests.get(drives_url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            
            drives_data = response.json()
            drives = drives_data.get('value', [])
            
            if not drives:
                logger.error("No drives found for site")
                return None
            
            drive_id = drives[0].get('id')
            
            # Download file content
            download_url = f"{self.graph_base_url}/sites/{site_id}/drives/{drive_id}/items/{file_id}/content"
            
            headers = self._get_headers()
            headers.pop('Content-Type', None)  # Remove Content-Type for binary download
            
            response = requests.get(download_url, headers=headers, timeout=60, stream=True)
            response.raise_for_status()
            
            file_content = response.content
            logger.info(f"Successfully downloaded file (size: {len(file_content)} bytes)")
            return file_content
            
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Graph API error details: {error_detail}")
                except:
                    logger.error(f"Graph API error response: {e.response.text}")
            return None

