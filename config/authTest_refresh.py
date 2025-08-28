import os
import sys
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 
          'https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/gmail.labels']

def test_gmail_credentials() -> bool:
    """Test and refresh Gmail credentials"""
    print("🔍 Testing Gmail Authentication...")
    
    creds = None
    token_path = 'data/gmail_token.pickle'
    credentials_path = 'config/credentials.json'
    
    # Check if credentials.json exists
    if not os.path.exists(credentials_path):
        print(f"❌ Credentials file not found: {credentials_path}")
        return False
    
    print(f"✅ Found credentials file: {credentials_path}")
    
    # Load existing token if it exists
    if os.path.exists(token_path):
        print(f"📂 Loading existing token from: {token_path}")
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    else:
        print(f"⚠️ No existing token found at: {token_path}")
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            try:
                creds.refresh(Request())
                print("✅ Token refreshed successfully!")
            except Exception as e:
                print(f"❌ Token refresh failed: {e}")
                print("🔑 Need to re-authenticate...")
                creds = None
        
        if not creds:
            print("🔑 Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES)
            creds = flow.run_local_server(port=8080)
            print("✅ Authentication completed!")
        
        # Save the credentials for the next run
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
        print(f"💾 Saved new token to: {token_path}")
    
    # Test the credentials by making a simple API call
    try:
        print("🧪 Testing Gmail API connection...")
        service = build('gmail', 'v1', credentials=creds)
        
        # Get user profile
        profile = service.users().getProfile(userId='me').execute()
        print(f"✅ Successfully connected to Gmail!")
        print(f"📧 Email: {profile.get('emailAddress')}")
        print(f"📊 Total messages: {profile.get('messagesTotal')}")
        
        # Test labels
        labels = service.users().labels().list(userId='me').execute()
        print(f"🏷️ Found {len(labels.get('labels', []))} labels")
        
        return True
        
    except Exception as e:
        print(f"❌ Gmail API test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_gmail_credentials()
    if success:
        print("\n🎉 Gmail authentication is working correctly!")
    else:
        print("\n❌ Gmail authentication needs to be fixed.")