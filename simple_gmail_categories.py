#!/usr/bin/env python3
"""
Simple Gmail Categories Retrieval
Just get Gmail labels with 1 API call and return them.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.gmail.gmail_organizer import GmailAIOrganizer
import json
from datetime import datetime

def get_gmail_categories():
    """Retrieve Gmail labels with exactly 1 API call"""
    try:
        print("🏷️ Retrieving Gmail categories...")
        
        # Initialize Gmail organizer
        organizer = GmailAIOrganizer(credentials_file='./config/credentials.json')
        
        # Authenticate
        if not organizer.authenticate():
            return {"status": "error", "message": "Gmail authentication failed"}
        
        # Make 1 API call to get all labels
        print("📞 Making Gmail API call to retrieve labels...")
        labels_result = organizer.service.users().labels().list(userId='me').execute()
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
        print(f"🔧 Custom labels: {[label['name'] for label in user_labels[:5]]}{'...' if len(user_labels) > 5 else ''}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    result = get_gmail_categories()
    print("\n" + "="*50)
    print(json.dumps(result, indent=2))
