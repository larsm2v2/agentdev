#!/usr/bin/env python3
"""
Ultra-Simple Gmail Categories Retrieval
Just Gmail API, no other dependencies.
"""

import os
import pickle
import json
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scopes - minimal required permissions
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.labels', 
    'https://www.googleapis.com/auth/gmail.modify'
]

def authenticate_gmail():
    """Authenticate with Gmail API"""
    creds = None
    
    # Token file paths
    token_paths = [
        './data/gmail_token.pickle',
        './data/token.json',
        './gmail_token.pickle',
        './token.json'
    ]
    
    # Try to load existing token
    for token_path in token_paths:
        if os.path.exists(token_path):
            print(f"🔑 Loading existing token from {token_path}")
            if token_path.endswith('.pickle'):
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
            elif token_path.endswith('.json'):
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            break
    
    # If there are no valid credentials, get them
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("🚀 Starting new OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                './config/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        print("💾 Saving credentials...")
        with open('./data/gmail_token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def get_gmail_categories():
    """Retrieve Gmail labels with exactly 1 API call"""
    try:
        print("🏷️ Retrieving Gmail categories...")
        
        # Authenticate
        creds = authenticate_gmail()
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

if __name__ == "__main__":
    result = get_gmail_categories()
    print("\n" + "="*50)
    print(json.dumps(result, indent=2))
