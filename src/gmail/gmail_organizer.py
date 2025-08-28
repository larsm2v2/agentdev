#!/usr/bin/env python3
"""
Gmail API Integration - Secure OAuth2 and Email Processing
"""

import os
import pickle
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import time
import base64
import email
from email.mime.text import MIMEText
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# Email reply parsing
email_reply_parser = None
try:
    # Try different import paths for email_reply_parser
    try:
        from . import email_reply_parser
        EMAIL_REPLY_PARSER_AVAILABLE = True
    except ImportError:
        try:
            from gmail import email_reply_parser
            EMAIL_REPLY_PARSER_AVAILABLE = True
        except ImportError:
            import gmail.email_reply_parser as email_reply_parser
            EMAIL_REPLY_PARSER_AVAILABLE = True
except ImportError:
    EMAIL_REPLY_PARSER_AVAILABLE = False
    print("ℹ️  email_reply_parser not available - using basic email cleaning")

# Try different import paths for direct_llm_providers
try:
    from ..core.direct_llm_providers import MultiLLMManager
except ImportError:
    from src.core.direct_llm_providers import MultiLLMManager

class GmailAIOrganizer:
    """Gmail AI-powered email organizer with multi-provider LLM support"""
    
    # Gmail API scopes - minimal required permissions
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.labels', 
        'https://www.googleapis.com/auth/gmail.modify'
    ]

    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "gmail_token.pickle"):
        """
        Initialize Gmail organizer
        
        Args:
            credentials_file: Path to OAuth2 credentials JSON file
        """
        self.credentials_file = credentials_file
        # honor caller-provided token_file path
        self.token_file = token_file
        self.service = None
        self.creds = None
        # optional per-organizer rate limiter (TokenBucket) will be attached by factory
        self.rate_limiter = None

        # Initialize AI chains with multi-provider support
        self.ai_manager = MultiLLMManager()

        # Email classification categories
        self.categories = {
            "Duke-related work": "DHVI, CFAR, and scientific research emails",
            "Emory-related work": "Emails from Emory contacts and Emory email recipients",
            "work": "Work-related emails, meetings, and projects",
            "family & friends": "Personal emails from Armands, McFarlands, and dance-related contacts",
            "personal": "Personal correspondence and private communications",
            "newsletters": "Newsletters, updates, and informational content",
            "subscriptions": "Subscription-based content and services",
            "updates": "Software updates, service notifications, and system messages",
            "marketing": "Marketing emails, promotional content, and advertisements",
            "deals": "Special offers, discounts, and deal notifications",
            "advertisements": "Commercial advertisements and promotional materials",
            "Banking": "Banking communications, account statements, and financial services",
            "bills": "Bills, invoices, and payment notifications",
            "financial statements": "Financial statements, reports, and account summaries",
            "travel confirmations": "Travel booking confirmations and reservations",
            "travel bookings": "Travel booking requests and itinerary planning",
            "travel itineraries": "Travel schedules, itineraries, and trip details",
            "Instagram": "Instagram notifications, posts, stories, and social updates",
            "LinkedIn": "LinkedIn professional networking, job updates, and career notifications",
            "Facebook": "Facebook social updates, event invitations, and friend notifications",
            "Twitter": "Twitter notifications, mentions, and social media updates",
            "YouTube": "YouTube video notifications, channel updates, and subscription content",
            "TikTok": "TikTok notifications, video updates, and social content",
            "social media": "General social media notifications and platform updates",
            "community": "Community forums, group discussions, and online communities",
            "events": "Event invitations, RSVPs, and social gathering notifications",
            "job alerts": "Job alerts and notifications from job boards and career sites",
            "job applications": "Job application confirmations and application status updates",
            "recruiter outreach": "Direct messages and outreach from recruiters and hiring managers",
            "interview scheduling": "Interview invitations, scheduling, and coordination emails",
            "job offers": "Job offers, salary negotiations, and employment contracts",
            "career networking": "Professional networking opportunities and career development",
            "LinkedIn jobs": "Job notifications and updates from LinkedIn",
            "Indeed jobs": "Job alerts and communications from Indeed",
            "Glassdoor jobs": "Job-related emails and company insights from Glassdoor",
            "ZipRecruiter jobs": "Job notifications and recruiter messages from ZipRecruiter",
            "Monster jobs": "Job alerts and career communications from Monster",
            "CareerBuilder jobs": "Job postings from university career centers and academic institutions",
            "AngelList jobs": "Startup job opportunities and notifications from AngelList",
            "Dice jobs": "Technology job alerts and communications from Dice",
            "FlexJobs": "Remote and flexible job opportunities from FlexJobs",
            "University careers": "Job postings from university career centers and academic institutions",
            "Company careers": "Direct job communications from company career pages",
            "spam": "Unwanted, suspicious, or junk emails",
            "important": "High priority emails requiring immediate attention"
        }

        print("🚀 Gmail AI Organizer initialized")
        print(f"🤖 Using {self.ai_manager.provider_type.value} for AI processing")
    
    def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using OAuth2
        
        Returns:
            bool: True if authentication successful
        """
        try:
            # Load existing token if present
            if os.path.exists(self.token_file):
                try:
                    with open(self.token_file, 'rb') as token:
                        self.creds = pickle.load(token)
                    print(f"📂 Loading existing token from: {self.token_file}")
                except Exception as e:
                    print(f"⚠️ Failed to load existing token, will re-auth: {e}")
                    self.creds = None

            # If no valid credentials, try refresh, otherwise perform interactive auth
            if not self.creds or not getattr(self.creds, 'valid', False):
                # Try refresh when possible, but recover on failure
                if self.creds and getattr(self.creds, 'expired', False) and getattr(self.creds, 'refresh_token', None):
                    try:
                        print("🔄 Refreshing expired credentials...")
                        self.creds.refresh(Request())
                        print("🔄 Token refreshed successfully")
                    except Exception as e:
                        print(f"⚠️ Token refresh failed, will attempt interactive auth: {e}")
                        self.creds = None

                if not self.creds or not getattr(self.creds, 'valid', False):
                    print("🔐 Starting OAuth2 authentication flow...")
                    if not os.path.exists(self.credentials_file):
                        print(f"❌ Credentials file not found: {self.credentials_file}")
                        print("📋 To get credentials:")
                        print("1. Go to Google Cloud Console")
                        print("2. Enable Gmail API")
                        print("3. Create OAuth2 credentials")
                        print("4. Download as 'credentials.json'")
                        return False

                    # Remove known-broken token file to force clean flow
                    try:
                        if os.path.exists(self.token_file):
                            os.remove(self.token_file)
                            print(f"⚠️ Removed broken token file to force re-auth: {self.token_file}")
                    except Exception:
                        pass

                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)

                # Persist credentials
                try:
                    os.makedirs(os.path.dirname(self.token_file) or '.', exist_ok=True)
                    with open(self.token_file, 'wb') as token:
                        pickle.dump(self.creds, token)
                    print("💾 Saved token to:", self.token_file)
                except Exception as e:
                    print(f"⚠️ Failed to save token: {e}")

            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=self.creds)
            print("✅ Gmail API authentication successful")
            return True

        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def get_email_content(self, message_id: str) -> Dict[str, Any]:
        """
        Extract and clean email content
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Dict with parsed email data
        """
        if not self.service:
            print("❌ Gmail service not authenticated. Please call authenticate() first.")
            return {}
        
        try:
            # Get full message
            message = self.service.users().messages().get(
                userId='me', id=message_id, format='full'
            ).execute()
            
            # Extract headers
            headers = {h['name']: h['value'] for h in message['payload']['headers']}
            
            # Extract body content
            body = self._extract_body(message['payload'])
            
            # Clean and parse body
            clean_body = self._clean_email_body(body)
            
            # Parse date
            date_received = date_parser.parse(headers.get('Date', ''))
            
            return {
                'id': message_id,
                'thread_id': message.get('threadId'),
                'subject': headers.get('Subject', ''),
                'sender': headers.get('From', ''),
                'recipient': headers.get('To', ''),
                'date': date_received,
                'body': clean_body,
                'raw_body': body,
                'labels': message.get('labelIds', []),
                'snippet': message.get('snippet', ''),
                'headers': headers
            }
            
        except HttpError as e:
            print(f"❌ Error fetching email {message_id}: {e}")
            return {}
    
    def _extract_body(self, payload: Dict) -> str:
        """Extract body text from email payload"""
        body = ""
        
        if 'parts' in payload:
            # Multipart message
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    if 'data' in part['body']:
                        html_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        # Convert HTML to text
                        soup = BeautifulSoup(html_body, 'html.parser')
                        body += soup.get_text()
        else:
            # Single part message
            if payload['mimeType'] == 'text/plain':
                if 'data' in payload['body']:
                    body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            elif payload['mimeType'] == 'text/html':
                if 'data' in payload['body']:
                    html_body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                    soup = BeautifulSoup(html_body, 'html.parser')
                    body = soup.get_text()
        
        return body
    
    def _clean_email_body(self, body: str) -> str:
        """Clean email body for AI processing"""
        try:
            # Remove reply chains and signatures
            if EMAIL_REPLY_PARSER_AVAILABLE and email_reply_parser is not None:
                # Use the email_reply_parser module to extract the original content
                clean = email_reply_parser.EmailReplyParser.parse_reply(body)
            else:
                # Basic cleaning without email_reply_parser
                # Remove common reply patterns
                lines = body.split('\n')
                clean_lines = []
                
                for line in lines:
                    # Skip common reply indicators
                    if any(indicator in line.lower() for indicator in [
                        'on ', 'wrote:', '-----original message-----', 
                        'from:', 'sent:', 'to:', 'subject:', '>', '>>>'
                    ]):
                        break
                    clean_lines.append(line)
                
                clean = '\n'.join(clean_lines)
            
            # Remove excessive whitespace
            clean = re.sub(r'\n\s*\n', '\n\n', clean)
            clean = re.sub(r' +', ' ', clean)
            
            # Truncate if too long (to manage API costs)
            if len(clean) > 2000:
                clean = clean[:2000] + "...[truncated]"
            
            return clean.strip()
            
        except Exception as e:
            print(f"⚠️  Email cleaning failed: {e}")
            return body[:2000]  # Fallback truncation
    
    def classify_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI to classify email into categories
        
        Args:
            email_data: Parsed email data
            
        Returns:
            Dict with classification results
        """
        try:
            # Prepare classification prompt
            classification_prompt = f"""
            Classify this email into the most appropriate category and suggest actions.
            
            Email Details:
            Subject: {email_data.get('subject', '')}
            From: {email_data.get('sender', '')}
            Content: {email_data.get('body', '')[:1000]}
            
            Available Categories:
            {json.dumps(self.categories, indent=2)}
            
            Provide your response as JSON with this exact structure:
            {{
                "category": "category_name",
                "confidence": 0.95,
                "reasoning": "Brief explanation of classification",
                "priority": "high|medium|low",
                "suggested_actions": ["action1", "action2"],
                "is_actionable": true,
                "contains_sensitive_info": false
            }}
            """
            
            # Get AI classification
            import asyncio
            response = asyncio.run(self.ai_manager.generate_response(classification_prompt))
            
            # Parse JSON response (handle markdown code blocks)
            try:
                # Clean up the response - remove markdown code blocks if present
                cleaned_response = response.strip()
                
                if cleaned_response.startswith('```'):
                    # Extract JSON from markdown code block
                    import re
                    # Use regex to extract content between ```json and ```
                    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', cleaned_response, re.DOTALL)
                    if json_match:
                        cleaned_response = json_match.group(1).strip()
                    else:
                        # Fallback: remove all ``` lines
                        lines = cleaned_response.split('\n')
                        json_lines = []
                        in_code_block = False
                        
                        for line in lines:
                            if line.strip().startswith('```'):
                                in_code_block = not in_code_block
                                continue
                            if in_code_block:
                                json_lines.append(line)
                        
                        cleaned_response = '\n'.join(json_lines)
                
                result = json.loads(cleaned_response)
                
                # Validate required fields
                if 'category' not in result:
                    result['category'] = 'personal'
                if 'confidence' not in result:
                    result['confidence'] = 0.5
                if 'priority' not in result:
                    result['priority'] = 'medium'
                
                return result
                
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"⚠️  Failed to parse AI response: {response[:200]}...")
                print(f"⚠️  Error: {str(e)}")
                return {
                    'category': 'personal',
                    'confidence': 0.3,
                    'reasoning': 'AI response parsing failed',
                    'priority': 'medium',
                    'suggested_actions': ['review_manually'],
                    'is_actionable': False,
                    'contains_sensitive_info': False
                }
                
        except Exception as e:
            print(f"❌ Email classification failed: {e}")
            return {
                'category': 'personal',
                'confidence': 0.1,
                'reasoning': f'Classification error: {str(e)}',
                'priority': 'medium',
                'suggested_actions': ['review_manually'],
                'is_actionable': False,
                'contains_sensitive_info': False
            }
    
    def get_recent_emails(self, max_results: int = 50, days_back: int = 7) -> List[str]:
        """
        Get recent email IDs for processing
        
        Args:
            max_results: Maximum number of emails to fetch
            days_back: How many days back to look
            
        Returns:
            List of message IDs
        """
        if not self.service:
            print("❌ Gmail service not authenticated. Please call authenticate() first.")
            return []
        
        try:
            # Calculate date range
            after_date = datetime.now() - timedelta(days=days_back)
            query = f'after:{after_date.strftime("%Y/%m/%d")}'
            
            # Search for messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return [msg['id'] for msg in messages]
            
        except HttpError as e:
            print(f"❌ Error fetching recent emails: {e}")
            return []

    def batch_get_messages(self, message_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch a list of messages in a single batch HTTP request (when supported by the client).

        Args:
            message_ids: List of Gmail message IDs

        Returns:
            List of parsed message dicts (same format as get_email_content)
        """
        if not self.service:
            print("❌ Gmail service not authenticated. Please call authenticate() first.")
            return []

        # Try to import BatchHttpRequest helper; if unavailable, fall back to sequential
        try:
            from googleapiclient.http import BatchHttpRequest  # noqa: F401
        except Exception:
            # Batch not available - fall back to sequential fetch
            results = []
            for mid in message_ids:
                msg = self.get_email_content(mid)
                if msg:
                    results.append(msg)
            return results

        # We'll accumulate parsed results keyed by message id so we can preserve input order
        parsed_by_id: Dict[str, Dict[str, Any]] = {}
        failed_ids: List[str] = []

        def _callback(request_id, response, exception):
            # request_id is the message id we set when adding the request
            mid = request_id
            try:
                if exception:
                    # mark as failed; the outer logic may retry
                    print(f"❌ Error fetching message in batch (id={mid}): {exception}")
                    failed_ids.append(mid)
                    return

                # parse response into same format as get_email_content
                headers = {h['name']: h['value'] for h in response.get('payload', {}).get('headers', [])}
                body = self._extract_body(response.get('payload', {}))
                clean_body = self._clean_email_body(body)
                try:
                    date_received = date_parser.parse(headers.get('Date', ''))
                except Exception:
                    date_received = None

                parsed = {
                    'id': response.get('id') or mid,
                    'thread_id': response.get('threadId'),
                    'subject': headers.get('Subject', ''),
                    'sender': headers.get('From', ''),
                    'recipient': headers.get('To', ''),
                    'date': date_received,
                    'body': clean_body,
                    'raw_body': body,
                    'labels': response.get('labelIds', []),
                    'snippet': response.get('snippet', ''),
                    'headers': headers
                }
                parsed_by_id[mid] = parsed
            except Exception as e:
                print(f"❌ Failed to parse batched message {mid}: {e}")
                failed_ids.append(mid)

        # Batch execution with simple retry/backoff for transient failures
        results: List[Dict[str, Any]] = []
        to_fetch = list(message_ids)
        max_attempts = 3
        attempt = 0

        while to_fetch and attempt < max_attempts:
            attempt += 1
            failed_ids = []
            batch = self.service.new_batch_http_request(callback=_callback)

            for mid in to_fetch:
                try:
                    req = self.service.users().messages().get(userId='me', id=mid, format='full')
                    # associate the request id so callback knows which message this is
                    batch.add(req, request_id=mid)
                except Exception as e:
                    print(f"❌ Failed to add message {mid} to batch: {e}")
                    failed_ids.append(mid)

            try:
                batch.execute()
            except HttpError as e:
                # If the entire batch failed, mark all as failed this round and retry
                print(f"❌ Batch execution failed on attempt {attempt}: {e}")
                # best-effort: if exception contains retry info, respect it
                try:
                    headers = getattr(e, 'resp', None) and getattr(e.resp, 'headers', None)
                    retry_after = None
                    if headers:
                        retry_after = headers.get('retry-after') or headers.get('Retry-After')
                    if retry_after:
                        wait = int(retry_after)
                    else:
                        wait = 2 ** attempt
                except Exception:
                    wait = 2 ** attempt

                time.sleep(wait)
                # schedule all for retry
                to_fetch = list(set(to_fetch))
                continue
            except Exception as e:
                # Non-HttpError - log and backoff a bit before retrying
                print(f"❌ Unexpected batch execution error on attempt {attempt}: {e}")
                wait = 2 ** attempt
                time.sleep(wait)
                to_fetch = list(set(to_fetch))
                continue

            # Prepare next round: any ids recorded as failed will be retried
            to_fetch = failed_ids

            if to_fetch:
                # exponential backoff before retrying
                wait = 2 ** attempt
                print(f"⏳ Retrying {len(to_fetch)} failed messages after {wait}s (attempt {attempt}/{max_attempts})")
                time.sleep(wait)

        # Build results preserving original order
        for mid in message_ids:
            if mid in parsed_by_id:
                results.append(parsed_by_id[mid])
            else:
                # skip missing messages (failed after retries)
                print(f"⚠️ Message {mid} failed to fetch after {max_attempts} attempts")

        return results
    
    def reprocess_existing_emails(self, batch_size: int = 50, log_file: str = "processed_emails_log.json", delete_old_labels: bool = True) -> Dict[str, Any]:
        """
        Reprocess already processed emails with new category system
        
        This function:
        1. Optionally deletes all existing AI labels (more efficient)
        2. Loads previously processed emails from log file
        3. Reclassifies emails with updated categories
        4. Applies new labels based on new classification
        5. Updates the log file with new classifications
        
        Args:
            batch_size: Number of emails to process in each batch
            log_file: Path to the processed emails log file
            delete_old_labels: If True, delete all AI labels at start (more efficient)
            
        Returns:
            Dict with reprocessing statistics
        """
        print("🔄 Starting email reprocessing with updated categories...")
        
        stats = {
            "total_found": 0,
            "successfully_reprocessed": 0,
            "failed_to_reprocess": 0,
            "skipped": 0,
            "categories_updated": {},
            "errors": [],
            "labels_deleted": 0
        }
        
        try:
            # Load existing processed emails log
            if not os.path.exists(log_file):
                print(f"❌ No processed emails log found at {log_file}")
                return stats
            
            with open(log_file, 'r') as f:
                log_data = json.load(f)
            
            # Handle both old and new log formats
            processed_emails = log_data.get('processed_emails', log_data) if isinstance(log_data, dict) else {}
            
            if not processed_emails:
                print("❌ No processed emails found in log")
                return stats
            
            stats["total_found"] = len(processed_emails)
            print(f"📊 Found {stats['total_found']} previously processed emails")
            
            # Ensure Gmail service is authenticated
            if not self.service:
                print("🔐 Authenticating with Gmail...")
                if not self.authenticate():
                    print("❌ Gmail authentication failed")
                    return stats
            
            # Optionally delete all existing AI labels first (more efficient)
            if delete_old_labels:
                print("🗑️  Deleting all existing AI labels first...")
                deletion_stats = self.delete_all_ai_labels()
                stats["labels_deleted"] = deletion_stats["labels_deleted"]
                if deletion_stats["deletion_errors"]:
                    stats["errors"].extend(deletion_stats["deletion_errors"])
            
            # Process emails in batches
            email_ids = list(processed_emails.keys())
            total_batches = (len(email_ids) + batch_size - 1) // batch_size
            
            print(f"🔄 Processing {len(email_ids)} emails in {total_batches} batches of {batch_size}")
            
            updated_log = {"processed_emails": {}}
            
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min((batch_num + 1) * batch_size, len(email_ids))
                batch_ids = email_ids[start_idx:end_idx]
                
                print(f"\n📦 Processing batch {batch_num + 1}/{total_batches} ({len(batch_ids)} emails)")
                
                for i, email_id in enumerate(batch_ids):
                    old_email_data = None  # Initialize to prevent unbound variable issues
                    
                    try:
                        print(f"  📧 Reprocessing email {i+1}/{len(batch_ids)} (ID: {email_id})")
                        
                        # Get current email data from log
                        old_email_data = processed_emails[email_id]
                        old_category = old_email_data.get('classification', {}).get('category', 'unknown')
                        
                        # Get fresh email content from Gmail
                        fresh_email_data = self.get_email_content(email_id)
                        
                        if not fresh_email_data:
                            print(f"    ⚠️  Could not fetch email content for {email_id}")
                            stats["skipped"] += 1
                            # Keep old data if can't fetch fresh
                            updated_log["processed_emails"][email_id] = old_email_data
                            continue
                        
                        # Remove existing Gmail labels (bulk deletion handles this)
                        # Individual label removal is skipped when delete_old_labels=True
                        if not delete_old_labels:
                            try:
                                self._remove_custom_labels(email_id, old_category)
                            except Exception as label_error:
                                print(f"    ⚠️  Could not remove old labels: {label_error}")
                        
                        # Reclassify with new category system
                        new_classification = self.classify_email(fresh_email_data)
                        new_category = new_classification.get('category', 'personal')
                        
                        # Apply new label
                        try:
                            self._apply_category_label(email_id, new_category)
                        except Exception as label_error:
                            print(f"    ⚠️  Could not apply new label: {label_error}")
                        
                        # Update log entry with new classification
                        updated_email_data = {
                            "id": email_id,
                            "subject": fresh_email_data.get('subject', ''),
                            "sender": fresh_email_data.get('sender', ''),
                            "date": fresh_email_data.get('date', '').isoformat() if hasattr(fresh_email_data.get('date', ''), 'isoformat') else str(fresh_email_data.get('date', '')),
                            "classification": new_classification,
                            "processed_at": datetime.now().isoformat(),
                            "reprocessed_at": datetime.now().isoformat(),
                            "old_category": old_category,
                            "reprocessing_version": "2.0"
                        }
                        
                        updated_log["processed_emails"][email_id] = updated_email_data
                        
                        # Update stats
                        stats["successfully_reprocessed"] += 1
                        
                        # Track category changes
                        if old_category != new_category:
                            change_key = f"{old_category} → {new_category}"
                            stats["categories_updated"][change_key] = stats["categories_updated"].get(change_key, 0) + 1
                        
                        print(f"    ✅ Recategorized: {old_category} → {new_category}")
                        
                    except Exception as e:
                        error_msg = f"Failed to reprocess email {email_id}: {str(e)}"
                        print(f"    ❌ {error_msg}")
                        stats["failed_to_reprocess"] += 1
                        stats["errors"].append(error_msg)
                        
                        # Keep old data on error
                        updated_log["processed_emails"][email_id] = old_email_data
                        continue
                
                # Save progress after each batch
                print(f"  💾 Saving progress after batch {batch_num + 1}...")
                with open(log_file, 'w') as f:
                    json.dump(updated_log, f, indent=2, default=str)
            
            # Final save and summary
            with open(log_file, 'w') as f:
                json.dump(updated_log, f, indent=2, default=str)
            
            print(f"\n✅ Reprocessing completed!")
            print(f"📊 Summary:")
            print(f"   Total emails found: {stats['total_found']}")
            print(f"   Successfully reprocessed: {stats['successfully_reprocessed']}")
            print(f"   Failed to reprocess: {stats['failed_to_reprocess']}")
            print(f"   Skipped: {stats['skipped']}")
            
            if stats["categories_updated"]:
                print(f"\n📈 Category changes:")
                for change, count in sorted(stats["categories_updated"].items(), key=lambda x: x[1], reverse=True):
                    print(f"   {change}: {count} emails")
            
            return stats
            
        except Exception as e:
            error_msg = f"Reprocessing failed: {str(e)}"
            print(f"❌ {error_msg}")
            stats["errors"].append(error_msg)
            return stats
    
    def _remove_custom_labels(self, email_id: str, old_category: str):
        """Remove custom labels that may have been applied based on old category"""
        if not self.service:
            print("❌ Gmail service not authenticated. Please call authenticate() first.")
            return
        
        try:
            # Create label name from old category (convert to Gmail-safe format)
            old_label_name = self._category_to_label_name(old_category)
            
            # Get all labels
            labels_result = self.service.users().labels().list(userId='me').execute()
            labels = labels_result.get('labels', [])
            
            # Find the old label ID
            old_label_id = None
            for label in labels:
                if label['name'] == old_label_name:
                    old_label_id = label['id']
                    break
            
            # Remove the old label if found
            if old_label_id:
                self.service.users().messages().modify(
                    userId='me',
                    id=email_id,
                    body={'removeLabelIds': [old_label_id]}
                ).execute()
                print(f"    🗑️  Removed old label: {old_label_name}")
            
        except Exception as e:
            # Non-critical error, log but don't fail the whole process
            print(f"    ⚠️  Could not remove old label: {e}")
    
    def delete_all_ai_labels(self) -> Dict[str, Any]:
        """
        Delete all AI-generated labels completely from Gmail
        This is more efficient than removing labels from individual emails
        
        Returns:
            Dict with deletion statistics
        """
        if not self.service:
            print("❌ Gmail service not authenticated. Please call authenticate() first.")
            return {"labels_found": 0, "labels_deleted": 0, "deletion_errors": ["Service not authenticated"]}
        
        print("🗑️  Deleting all existing AI-generated labels...")
        
        stats = {
            "labels_found": 0,
            "labels_deleted": 0,
            "deletion_errors": []
        }
        
        try:
            # Get all labels
            labels_result = self.service.users().labels().list(userId='me').execute()
            labels = labels_result.get('labels', [])
            
            # Find all AI-generated labels (old and new formats)
            ai_labels = []
            for label in labels:
                label_name = label.get('name', '')
                # Check for all AI label formats: AI_Category_, (AICat), and a_
                if (label_name.startswith('AI_Category_') or 
                    label_name.endswith('(AICat)') or 
                    label_name.startswith('a_')):
                    ai_labels.append(label)
            
            stats["labels_found"] = len(ai_labels)
            print(f"📊 Found {len(ai_labels)} AI-generated labels to delete")
            
            # Delete each AI label
            for label in ai_labels:
                label_name = label.get('name', '')  # Initialize outside try block
                
                try:
                    label_id = label.get('id', '')
                    
                    print(f"  🗑️  Deleting label: {label_name}")
                    
                    # Delete the label (this removes it from all emails automatically)
                    self.service.users().labels().delete(
                        userId='me',
                        id=label_id
                    ).execute()
                    
                    stats["labels_deleted"] += 1
                    print(f"    ✅ Deleted: {label_name}")
                    
                except Exception as label_error:
                    error_msg = f"Failed to delete label {label_name}: {str(label_error)}"
                    print(f"    ❌ {error_msg}")
                    stats["deletion_errors"].append(error_msg)
            
            print(f"\n✅ Label deletion complete!")
            print(f"📊 Deleted {stats['labels_deleted']} out of {stats['labels_found']} AI labels")
            
            return stats
            
        except Exception as e:
            error_msg = f"Label deletion failed: {str(e)}"
            print(f"❌ {error_msg}")
            stats["deletion_errors"].append(error_msg)
            return stats
    
    def _apply_category_label(self, email_id: str, category: str):
        """Apply Gmail label based on new category"""
        if not self.service:
            print("❌ Gmail service not authenticated. Please call authenticate() first.")
            return
        
        try:
            # Create label name from category
            label_name = self._category_to_label_name(category)
            
            # Get or create the label
            label_id = self._get_or_create_label(label_name)
            
            # Apply the label
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            
            print(f"    🏷️  Applied new label: {label_name}")
            
        except Exception as e:
            # Non-critical error, log but don't fail the whole process
            print(f"    ⚠️  Could not apply new label: {e}")
    
    def _category_to_label_name(self, category: str) -> str:
        """Convert category name to Gmail-safe label name"""
        # Clean the category name and make it Gmail-safe
        clean_category = category.strip().lower()
        # Replace spaces and special characters with underscores
        clean_category = re.sub(r'[&]', 'and', clean_category)  # Replace & with 'and'
        clean_category = re.sub(r'[^\w\s\-]', '', clean_category)  # Remove special chars
        clean_category = re.sub(r'\s+', '_', clean_category)  # Replace spaces with underscores
        clean_category = re.sub(r'_+', '_', clean_category)  # Remove multiple underscores
        clean_category = clean_category.strip('_')  # Remove leading/trailing underscores
        # Add the a_ prefix
        return f"a_{clean_category}"
    
    def _get_or_create_label(self, label_name: str) -> str:
        """Get existing label ID or create new label"""
        if not self.service:
            print("❌ Gmail service not authenticated. Please call authenticate() first.")
            raise Exception("Gmail service not authenticated")
        
        try:
            # Get all labels
            labels_result = self.service.users().labels().list(userId='me').execute()
            labels = labels_result.get('labels', [])
            
            # Check if label already exists
            for label in labels:
                if label['name'] == label_name:
                    return label['id']
            
            # Create new label if it doesn't exist
            label_object = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            
            created_label = self.service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()
            
            return created_label['id']
            
        except Exception as e:
            print(f"    ⚠️  Error creating/getting label {label_name}: {e}")
            raise

def main():
    """Test the Gmail integration"""
    print("🧪 Testing Gmail AI Organizer...")
    
    # Initialize organizer
    organizer = GmailAIOrganizer()
    
    # Test authentication
    if not organizer.authenticate():
        print("❌ Authentication failed. Cannot proceed.")
        return
    
    print("✅ Authentication successful!")
    
    # Ask user what they want to do
    print("\n📋 What would you like to do?")
    print("1. Test recent email classification")
    print("2. Reprocess existing emails with new categories")
    print("3. Both")
    
    choice = input("Enter your choice (1, 2, or 3): ").strip()
    
    if choice in ['1', '3']:
        print("\n📧 Fetching recent emails for testing...")
        
        # Get a few recent emails
        email_ids = organizer.get_recent_emails(max_results=3)
        print(f"📥 Found {len(email_ids)} recent emails")
        
        # Process first email as test
        if email_ids:
            print(f"\n🔍 Analyzing first email...")
            email_data = organizer.get_email_content(email_ids[0])
            
            if email_data:
                print(f"📧 Subject: {email_data.get('subject', 'No subject')}")
                print(f"👤 From: {email_data.get('sender', 'Unknown')}")
                print(f"📅 Date: {email_data.get('date', 'Unknown')}")
                
                # Classify email
                classification = organizer.classify_email(email_data)
                print(f"\n🎯 AI Classification:")
                print(f"   Category: {classification.get('category', 'unknown')}")
                print(f"   Confidence: {classification.get('confidence', 0):.2f}")
                print(f"   Priority: {classification.get('priority', 'unknown')}")
                print(f"   Reasoning: {classification.get('reasoning', 'No reasoning')}")
    
    if choice in ['2', '3']:
        print("\n🔄 Starting email reprocessing...")
        
        # Ask for batch size
        try:
            batch_size = int(input("Enter batch size (default 25): ").strip() or "25")
        except ValueError:
            batch_size = 25
        
        # Start reprocessing (default to bulk label deletion)
        stats = organizer.reprocess_existing_emails(batch_size=batch_size, delete_old_labels=True)
        
        print(f"\n📊 Final Reprocessing Statistics:")
        print(f"   Total emails found: {stats['total_found']}")
        print(f"   Successfully reprocessed: {stats['successfully_reprocessed']}")
        print(f"   Failed: {stats['failed_to_reprocess']}")
        print(f"   Skipped: {stats['skipped']}")
        
        if stats['errors']:
            print(f"\n❌ Errors encountered:")
            for error in stats['errors'][:5]:  # Show first 5 errors
                print(f"   - {error}")
            if len(stats['errors']) > 5:
                print(f"   ... and {len(stats['errors']) - 5} more errors")


def reprocess_emails_standalone():
    """Standalone function for reprocessing emails with new categories"""
    print("🔄 Gmail Email Reprocessing Tool")
    print("=" * 50)
    print("This tool will reprocess all previously classified emails")
    print("with the new comprehensive category system.")
    print("=" * 50)
    
    # Initialize organizer
    print("\n🚀 Initializing Gmail AI Organizer...")
    organizer = GmailAIOrganizer()
    
    # Test authentication
    print("🔐 Authenticating with Gmail...")
    if not organizer.authenticate():
        print("❌ Authentication failed. Cannot proceed.")
        return
    
    print("✅ Authentication successful!")
    
    # Ask for confirmation
    print(f"\n⚠️  This will reprocess ALL previously classified emails.")
    print(f"📊 Current categories include: {len(organizer.categories)} categories")
    print(f"🏷️  Old Gmail labels will be removed and new ones applied.")
    
    confirm = input("\nDo you want to continue? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Reprocessing cancelled.")
        return
    
    # Ask for batch size
    try:
        batch_size = int(input("Enter batch size (default 25, max 100): ").strip() or "25")
        batch_size = min(max(batch_size, 1), 100)  # Clamp between 1 and 100
    except ValueError:
        batch_size = 25
    
    print(f"\n🔄 Starting reprocessing with batch size: {batch_size}")
    
    # Start reprocessing
    stats = organizer.reprocess_existing_emails(batch_size=batch_size)
    
    # Final summary
    print(f"\n" + "=" * 50)
    print(f"📊 REPROCESSING COMPLETE")
    print(f"=" * 50)
    print(f"Total emails found: {stats['total_found']}")
    print(f"Successfully reprocessed: {stats['successfully_reprocessed']}")
    print(f"Failed to reprocess: {stats['failed_to_reprocess']}")
    print(f"Skipped: {stats['skipped']}")
    
    if stats['categories_updated']:
        print(f"\n📈 Top category changes:")
        sorted_changes = sorted(stats['categories_updated'].items(), key=lambda x: x[1], reverse=True)
        for change, count in sorted_changes[:10]:  # Show top 10 changes
            print(f"   {change}: {count} emails")
    
    if stats['errors']:
        print(f"\n❌ Errors encountered: {len(stats['errors'])}")
        if input("Show error details? (y/N): ").strip().lower() == 'y':
            for error in stats['errors']:
                print(f"   - {error}")
    
    print(f"\n✅ Reprocessing completed! Check your Gmail for updated labels.")
    print(f"🏷️  New labels use 'a_' prefix format (e.g., 'a_work', 'a_job_alerts')")


if __name__ == "__main__":
    import sys
    
    # Check if running in reprocessing mode
    if len(sys.argv) > 1 and sys.argv[1] == "--reprocess":
        reprocess_emails_standalone()
    else:
        main()
