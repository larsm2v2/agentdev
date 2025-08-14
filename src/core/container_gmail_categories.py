#!/usr/bin/env python3
"""
Container-compatible Gmail Categories for Enhanced Email Librarian Server
Direct Gmail API integration with minimal dependencies and comprehensive storage.
"""

import os
import pickle
import json
import uuid
import asyncio
import requests
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Import storage manager
try:
    from .gmail_storage_manager import store_gmail_api_result, get_cached_gmail_result
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    print("⚠️ Gmail Storage Manager not available")
    
    # Create dummy functions to avoid import errors
    async def store_gmail_api_result(call_type: str, query: str, emails: List[Dict], 
                                   api_calls_used: int = 1, metadata: Optional[Dict] = None, 
                                   execution_time_ms: Optional[int] = None) -> Optional[int]:
        return None
    
    async def get_cached_gmail_result(call_type: str, query: str) -> Optional[Dict]:
        return None

# Gmail API scopes - minimal required permissions
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.labels', 
    'https://www.googleapis.com/auth/gmail.modify'
]

class ContainerGmailCategories:
    """Container-compatible Gmail categories retrieval"""
    
    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        # Container-aware paths
        self.credentials_path = credentials_path or os.environ.get('GMAIL_CREDENTIALS_PATH', '/app/config/credentials.json')
        self.token_path = token_path or os.environ.get('GMAIL_TOKEN_PATH', '/app/data/gmail_token.pickle')
        
        # Fallback paths for different environments
        self.fallback_creds_paths = [
            self.credentials_path,
            './config/credentials.json',
            '/app/config/credentials.json',
            './credentials.json'
        ]
        
        self.fallback_token_paths = [
            self.token_path,
            './data/gmail_token.pickle',
            '/app/data/gmail_token.pickle',
            './data/token.json',
            '/app/data/token.json',
            './gmail_token.pickle',
            './token.json'
        ]
    
    def authenticate_gmail(self) -> Optional[Credentials]:
        """Authenticate with Gmail API - container compatible"""
        creds = None
        
        # Try to load existing token
        for token_path in self.fallback_token_paths:
            if os.path.exists(token_path):
                print(f"🔑 Loading existing token from {token_path}")
                try:
                    if token_path.endswith('.pickle'):
                        with open(token_path, 'rb') as token:
                            creds = pickle.load(token)
                    elif token_path.endswith('.json'):
                        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                    break
                except Exception as e:
                    print(f"⚠️ Could not load token from {token_path}: {e}")
                    continue
        
        # If there are no valid credentials, get them
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Refreshing expired credentials...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"❌ Token refresh failed: {e}")
                    creds = None
            
            if not creds:
                print("🚀 Starting new OAuth flow...")
                # Find credentials file
                creds_file = None
                for creds_path in self.fallback_creds_paths:
                    if os.path.exists(creds_path):
                        creds_file = creds_path
                        print(f"📁 Using credentials file: {creds_file}")
                        break
                
                if not creds_file:
                    raise FileNotFoundError(f"Gmail credentials not found in any of: {self.fallback_creds_paths}")
                
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                # Use local server auth (most compatible)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            print("💾 Saving credentials...")
            try:
                # Create directory if it doesn't exist
                token_dir = os.path.dirname(self.token_path)
                os.makedirs(token_dir, exist_ok=True)
                
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
                print(f"✅ Token saved to {self.token_path}")
            except Exception as e:
                print(f"⚠️ Could not save token to {self.token_path}: {e}")
        
        # Ensure only google.oauth2.credentials.Credentials or None is returned
        if isinstance(creds, Credentials):
            return creds
        else:
            return None
    
    def get_batch_emails_with_fields(self, batch_size: int = 50, query: Optional[str] = None) -> Dict[str, Any]:
        """Get emails using proper Gmail batch HTTP request with multipart/mixed format"""
        try:
            import requests
            import uuid
            
            print(f"⚡ PROPER BATCH-HTTP: Using direct HTTP batch request for {batch_size} emails...")
            
            # Authenticate
            creds = self.authenticate_gmail()
            if not creds:
                return {"status": "error", "message": "Gmail authentication failed"}
            
            # Build Gmail service for getting message IDs
            service = build('gmail', 'v1', credentials=creds)
            print("✅ Gmail service initialized")
            
            # Prepare query parameters
            api_query = query if query else 'in:inbox'
            
            # Step 1: Get email IDs (1 API call)
            print(f"📞 Getting email IDs with query: '{api_query}'")
            results = service.users().messages().list(
                userId='me',
                q=api_query,
                maxResults=batch_size
            ).execute()
            
            message_ids = [msg['id'] for msg in results.get('messages', [])]
            
            if not message_ids:
                return {
                    "status": "success", 
                    "emails": [], 
                    "summary": {"total": 0, "api_calls": 1, "method": "proper_batch_http_multipart"}
                }
            
            print(f"✅ Retrieved {len(message_ids)} email IDs")
            
            # Step 2: Create proper batch HTTP request using multipart/mixed
            boundary = f"batch_{uuid.uuid4().hex}"
            
            # Build the multipart/mixed body
            batch_body = ""
            
            for i, message_id in enumerate(message_ids):
                # Add boundary
                batch_body += f"--{boundary}\r\n"
                batch_body += "Content-Type: application/http\r\n"
                batch_body += f"Content-ID: <item{i}>\r\n\r\n"
                
                # Add the actual HTTP request
                batch_body += f"GET /gmail/v1/users/me/messages/{message_id}?format=metadata&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=Date HTTP/1.1\r\n"
                batch_body += "\r\n"
            
            # Close the batch
            batch_body += f"--{boundary}--\r\n"
            
            # Make the batch HTTP request
            headers = {
                'Authorization': f'Bearer {creds.token}',
                'Content-Type': f'multipart/mixed; boundary={boundary}',
                'Content-Length': str(len(batch_body))
            }
            
            print(f"� DEBUG: Request headers:")
            for key, value in headers.items():
                if key == 'Authorization':
                    print(f"   {key}: Bearer {value[-20:]}...")  # Only show last 20 chars of token
                else:
                    print(f"   {key}: {value}")
            
            print(f"�📞 Executing proper Gmail batch HTTP request for {len(message_ids)} emails...")
            
            # Send to Gmail's batch endpoint
            batch_url = "https://www.googleapis.com/batch/gmail/v1"
            
            response = requests.post(batch_url, headers=headers, data=batch_body)
            
            if response.status_code != 200:
                return {
                    "status": "error", 
                    "message": f"Batch request failed: {response.status_code} - {response.text[:200]}..."
                }
            
            # Parse the multipart response using the boundary from response headers
            batch_emails = []
            response_text = response.text
            
            # Extract boundary from response headers
            content_type = response.headers.get('content-type', '')
            response_boundary = None
            if 'boundary=' in content_type:
                response_boundary = content_type.split('boundary=')[1].strip()
            
            if response_boundary and f'--{response_boundary}' in response_text:
                # Split by the response boundary
                parts = response_text.split(f'--{response_boundary}')
                
                # Analyze each part
                for i, part in enumerate(parts):
                    if 'HTTP/1.1 200 OK' in part and 'application/json' in part:
                        
                        # Find the complete JSON object for the email
                        # The JSON starts after the HTTP headers (after a blank line)
                        lines = part.split('\n')
                        json_started = False
                        json_lines = []
                        brace_count = 0
                        
                        for line in lines:
                            line = line.strip()
                            
                            # Skip until we find the start of JSON (after blank line following headers)
                            if not json_started and line.startswith('{'):
                                json_started = True
                                json_lines = [line]
                                brace_count = line.count('{') - line.count('}')
                            elif json_started:
                                json_lines.append(line)
                                brace_count += line.count('{') - line.count('}')
                                
                                # When braces are balanced, we have a complete JSON object
                                if brace_count == 0:
                                    json_content = '\n'.join(json_lines)
                                    
                                    try:
                                        email_data = json.loads(json_content)
                                        
                                        # This should be a complete email object with id, threadId, payload, etc.
                                        if 'id' in email_data and 'payload' in email_data:
                                            processed_email = {
                                                "id": email_data.get('id'),
                                                "threadId": email_data.get('threadId'),
                                                "labelIds": email_data.get('labelIds', []),
                                                "subject": self._extract_subject_from_headers(email_data),
                                                "from": self._extract_from_headers(email_data),
                                                "date": self._extract_date_from_headers(email_data),
                                                "snippet": email_data.get('snippet', ''),
                                                "optimization": "proper_batch_http_multipart"
                                            }
                                            batch_emails.append(processed_email)
                                            print(f"✅ Successfully parsed complete email: {processed_email['id']}")
                                        else:
                                            print(f"⚠️ JSON object missing required fields (id/payload): {list(email_data.keys())}")
                                            
                                    except Exception as parse_error:
                                        print(f"❌ JSON parsing error for complete object: {parse_error}")
                                        print(f"   JSON content preview: {json_content[:200]}...")
                                    
                                    break  # Found complete JSON, move to next part
            else:
                print(f"❌ Could not find response boundary in headers or response text")
                print(f"   Content-Type: {content_type}")
                print(f"   Response preview: {response_text[:500]}...")
            
            print(f"✅ Successfully parsed {len(batch_emails)} emails from batch response")
            
            return {
                "status": "success",
                "emails": batch_emails,
                "summary": {
                    "total": len(batch_emails),
                    "api_calls": 2,  # 1 for list + 1 for batch
                    "http_requests": 2,
                    "method": "proper_batch_http_multipart",
                    "optimization_notes": [
                        "Uses direct HTTP POST to Gmail's /batch endpoint",
                        "Uses multipart/mixed content type per Gmail API docs",
                        "Uses format=metadata to avoid full message body",
                        "Fetches only Subject, From, Date headers",
                        "Multiple API calls bundled into single HTTP request"
                    ]
                }
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"status": "error", "message": str(e)}

    def _extract_subject_from_headers(self, message):
        """Extract subject from metadata headers"""
        headers = message.get('payload', {}).get('headers', [])
        for header in headers:
            if header.get('name', '').lower() == 'subject':
                return header.get('value', 'No Subject')
        return 'No Subject'

    def _extract_from_headers(self, message):
        """Extract from field from metadata headers"""
        headers = message.get('payload', {}).get('headers', [])
        for header in headers:
            if header.get('name', '').lower() == 'from':
                return header.get('value', 'Unknown Sender')
        return 'Unknown Sender'

    def _extract_date_from_headers(self, message):
        """Extract date from metadata headers"""
        headers = message.get('payload', {}).get('headers', [])
        for header in headers:
            if header.get('name', '').lower() == 'date':
                return header.get('value', 'Unknown Date')
        return 'Unknown Date'

    def get_gmail_categories(self) -> Dict[str, Any]:
        """Retrieve Gmail labels with exactly 1 API call"""
        try:
            print("🏷️ Retrieving Gmail categories...")
            
            # Authenticate
            creds = self.authenticate_gmail()
            if not creds:
                return {"status": "error", "message": "Gmail authentication failed"}
            
            # Build Gmail service
            service = build('gmail', 'v1', credentials=creds)
            print("✅ Gmail service initialized")
            
            # Make 1 API call to get all labels
            print("📞 Making Gmail API call to retrieve labels...")
            labels_result = service.users().labels().list(userId='me').execute()
            labels = labels_result.get('labels', [])
            
            print(f"✅ Retrieved {len(labels)} labels from Gmail")
            
            # Separate system labels from user-created labels
            system_labels = []
            user_labels = []
            
            for label in labels:
                label_info = {
                    'id': label['id'],
                    'name': label['name'],
                    'type': label.get('type', 'user'),
                    'messagesTotal': label.get('messagesTotal', 0),
                    'messagesUnread': label.get('messagesUnread', 0)
                }
                
                if label.get('type') == 'system':
                    system_labels.append(label_info)
                else:
                    user_labels.append(label_info)
            
            # Results
            result = {
                'status': 'success',
                'api_calls_used': 1,
                'retrieved_at': datetime.now().isoformat(),
                'summary': {
                    'total_labels': len(labels),
                    'user_created': len(user_labels),
                    'system_labels': len(system_labels)
                },
                'categories': {
                    'system_labels': system_labels,
                    'user_labels': user_labels,
                    'total_count': len(labels)
                }
            }
            
            print(f"📊 Summary: {len(labels)} total labels ({len(user_labels)} custom, {len(system_labels)} system)")
            if user_labels:
                print(f"🔧 Custom labels: {[label['name'] for label in user_labels[:5]]}{'...' if len(user_labels) > 5 else ''}")
            else:
                print("📝 No custom labels found")
            
            return result
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_batch_emails_with_storage(self, batch_size: int = 50, query: Optional[str] = None) -> Dict[str, Any]:
        """Enhanced batch email retrieval with comprehensive storage in PostgreSQL, Qdrant, and Redis"""
        start_time = time.time()
        
        try:
            print(f"🚀 STORAGE-ENABLED: Retrieving {batch_size} emails with full storage integration...")
            
            # Check Redis cache first
            if STORAGE_AVAILABLE:
                cached_result = await get_cached_gmail_result("batch_emails_with_fields", query or "in:inbox")
                if cached_result:
                    print(f"⚡ Using cached result from Redis ({cached_result['count']} emails)")
                    return {
                        "status": "success",
                        "emails": cached_result["emails"],
                        "summary": {
                            "total": cached_result["count"],
                            "source": "redis_cache",
                            "cached_at": cached_result["timestamp"]
                        }
                    }
            
            # Get emails using existing efficient method
            result = self.get_batch_emails_with_fields(batch_size, query)
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            if result["status"] == "success" and result["emails"] and STORAGE_AVAILABLE:
                print(f"💾 Storing {len(result['emails'])} emails in all storage systems...")
                
                # Store the API call result in PostgreSQL, Qdrant, and Redis
                api_call_id = await store_gmail_api_result(
                    call_type="batch_emails_with_fields",
                    query=query or "in:inbox",
                    emails=result["emails"],
                    api_calls_used=result["summary"]["api_calls"],
                    metadata={
                        **result["summary"],
                        "batch_size_requested": batch_size,
                        "query_used": query or "in:inbox",
                        "execution_time_ms": execution_time_ms
                    },
                    execution_time_ms=execution_time_ms
                )
                
                # Add storage info to result
                result["storage"] = {
                    "api_call_id": api_call_id,
                    "stored_in": ["postgresql", "qdrant", "redis"],
                    "storage_timestamp": datetime.now().isoformat(),
                    "storage_enabled": True
                }
                
                print(f"✅ Storage complete: API call ID {api_call_id}")
                
            elif not STORAGE_AVAILABLE:
                result["storage"] = {
                    "storage_enabled": False,
                    "message": "Storage manager not available"
                }
            
            return result
            
        except Exception as e:
            print(f"❌ Storage-enabled retrieval error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_gmail_categories_with_storage(self) -> Dict[str, Any]:
        """Enhanced Gmail categories retrieval with storage"""
        start_time = time.time()
        
        try:
            print("🏷️ STORAGE-ENABLED: Retrieving Gmail categories with storage...")
            
            # Check cache first
            if STORAGE_AVAILABLE:
                cached_result = await get_cached_gmail_result("gmail_categories", "all_labels")
                if cached_result:
                    print(f"⚡ Using cached categories from Redis")
                    return {
                        "status": "success",
                        "categories": cached_result.get("categories", {}),
                        "summary": cached_result.get("summary", {}),
                        "source": "redis_cache"
                    }
            
            # Get categories using existing method
            result = self.get_gmail_categories()
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            if result["status"] == "success" and STORAGE_AVAILABLE:
                print("💾 Storing Gmail categories...")
                
                # Prepare labels data for storage
                all_labels = result["categories"]["system_labels"] + result["categories"]["user_labels"]
                
                # Store categories
                api_call_id = await store_gmail_api_result(
                    call_type="gmail_categories",
                    query="all_labels",
                    emails=[],  # No emails for categories call
                    api_calls_used=result["api_calls_used"],
                    metadata={
                        **result["summary"],
                        "labels": all_labels,
                        "execution_time_ms": execution_time_ms
                    },
                    execution_time_ms=execution_time_ms
                )
                
                result["storage"] = {
                    "api_call_id": api_call_id,
                    "stored_in": ["postgresql", "redis"],
                    "storage_timestamp": datetime.now().isoformat(),
                    "storage_enabled": True
                }
                
            elif not STORAGE_AVAILABLE:
                result["storage"] = {
                    "storage_enabled": False,
                    "message": "Storage manager not available"
                }
            
            return result
            
        except Exception as e:
            print(f"❌ Storage-enabled categories error: {e}")
            return {"status": "error", "message": str(e)}

# Standalone function for easy import
def get_container_gmail_categories() -> Dict[str, Any]:
    """Get Gmail categories - container compatible"""
    gmail_cat = ContainerGmailCategories()
    return gmail_cat.get_gmail_categories()

def get_container_batch_emails_with_fields(batch_size: int = 50, query: Optional[str] = None) -> Dict[str, Any]:
    """Get batch of emails with field selection (ID, subject, labels) - container compatible"""
    gmail_cat = ContainerGmailCategories()
    return gmail_cat.get_batch_emails_with_fields(batch_size, query)

# Enhanced storage-enabled functions
async def get_container_batch_emails_with_storage(batch_size: int = 50, query: Optional[str] = None) -> Dict[str, Any]:
    """Get batch of emails with comprehensive storage in PostgreSQL, Qdrant, and Redis"""
    gmail_cat = ContainerGmailCategories()
    return await gmail_cat.get_batch_emails_with_storage(batch_size, query)

async def get_container_gmail_categories_with_storage() -> Dict[str, Any]:
    """Get Gmail categories with storage in PostgreSQL and Redis"""
    gmail_cat = ContainerGmailCategories()
    return await gmail_cat.get_gmail_categories_with_storage()

# Convenience function for semantic email search
async def search_emails_by_content(query_text: str, limit: int = 10) -> List[Dict]:
    """Search emails using semantic similarity (requires storage system)"""
    if not STORAGE_AVAILABLE:
        print("⚠️ Semantic search requires storage manager")
        return []
    
    try:
        from .gmail_storage_manager import search_emails_semantic
        return await search_emails_semantic(query_text, limit)
    except Exception as e:
        print(f"❌ Semantic search error: {e}")
        return []

if __name__ == "__main__":
    result = get_container_gmail_categories()
    print("\n" + "="*50)
    print(json.dumps(result, indent=2))
