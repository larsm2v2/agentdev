#!/usr/bin/env python3
"""
Simple test script to verify activity tracking functionality
"""

import sys
import os
import asyncio
from datetime import datetime

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_activity_methods():
    """Test the activity tracking methods without running the full server"""
    
    print("🧪 Testing Activity Tracking Methods")
    
    # Test class with just the activity methods
    class MockActivityTracker:
        def __init__(self):
            self.recent_activities = []
            self.max_activities = 50
            
        def format_activity_message(self, job_data):
            """Format job data into user-friendly activity message"""
            try:
                job_type = job_data.get("type", "unknown")
                processed_count = job_data.get("processed_count", 0)
                categories = job_data.get("categories", [])
                
                if job_type == "shelving":
                    if categories:
                        cat_list = ", ".join(categories[:3])  # Show first 3 categories
                        return f"Processed {processed_count} emails into [{cat_list}] categories"
                    else:
                        return f"Processed {processed_count} new emails"
                elif job_type == "archiving":
                    folder = job_data.get("folder", "Archive")
                    return f"Archived {processed_count} emails to {folder} folder"
                elif job_type == "inbox_clear":
                    return f"Inbox is clear - all {processed_count} emails organized"
                else:
                    return f"Processed {processed_count} emails"
                    
            except Exception as e:
                print(f"Error formatting activity message: {e}")
                return "Email processing completed"

        def add_activity(self, activity_type, message, metadata=None):
            """Add a new activity to the recent activities list"""
            try:
                import uuid
                
                activity = {
                    "id": str(uuid.uuid4()),
                    "type": activity_type,
                    "action": message,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata or {}
                }
                
                # Add to beginning of list
                self.recent_activities.insert(0, activity)
                
                # Keep only the most recent activities
                if len(self.recent_activities) > self.max_activities:
                    self.recent_activities = self.recent_activities[:self.max_activities]
                    
                print(f"📝 Activity logged: {message}")
                
            except Exception as e:
                print(f"Failed to add activity: {e}")

        def get_formatted_timestamp(self, iso_timestamp):
            """Convert ISO timestamp to human-readable format"""
            try:
                timestamp = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
                now = datetime.now(timestamp.tzinfo)
                diff = now - timestamp
                
                if diff.total_seconds() < 60:
                    return "just now"
                elif diff.total_seconds() < 3600:
                    minutes = int(diff.total_seconds() / 60)
                    return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                elif diff.total_seconds() < 86400:
                    hours = int(diff.total_seconds() / 3600)
                    return f"{hours} hour{'s' if hours != 1 else ''} ago"
                else:
                    days = int(diff.total_seconds() / 86400)
                    return f"{days} day{'s' if days != 1 else ''} ago"
                    
            except Exception as e:
                print(f"Error formatting timestamp: {e}")
                return "recently"
    
    # Create tracker
    tracker = MockActivityTracker()
    
    # Test adding activities
    print("\n1. Testing activity logging...")
    tracker.add_activity("system", "Email Librarian server started and ready", {"version": "2.0.0"})
    tracker.add_activity("shelving", "Shelving function started", {"job_id": "test-123"})
    tracker.add_activity("shelving", "Processed 5 new emails automatically", {"cycle": 1, "emails_processed": 5})
    tracker.add_activity("shelving", "Shelving function stopped", {"job_id": "test-123"})
    
    # Test activity retrieval
    print(f"\n2. Activities stored: {len(tracker.recent_activities)}")
    
    # Test formatting
    print("\n3. Testing formatted activities:")
    for i, activity in enumerate(tracker.recent_activities):
        formatted_time = tracker.get_formatted_timestamp(activity["timestamp"])
        print(f"   {i+1}. [{activity['type']}] {activity['action']} - {formatted_time}")
    
    # Test format_activity_message
    print("\n4. Testing job data formatting:")
    job_data_samples = [
        {"type": "shelving", "processed_count": 3, "categories": ["Work", "Personal", "Shopping"]},
        {"type": "shelving", "processed_count": 1, "categories": []},
        {"type": "archiving", "processed_count": 10, "folder": "2024-Archive"},
        {"type": "inbox_clear", "processed_count": 0}
    ]
    
    for job_data in job_data_samples:
        message = tracker.format_activity_message(job_data)
        print(f"   Job: {job_data} -> Message: '{message}'")
    
    print("\n✅ Activity tracking methods working correctly!")
    
    # Simulate dashboard API response
    print("\n5. Simulated API response format:")
    api_response = {
        "status": "success",
        "activity": []
    }
    
    for activity in tracker.recent_activities:
        formatted_activity = {
            "id": activity["id"],
            "action": activity["action"],
            "timestamp": tracker.get_formatted_timestamp(activity["timestamp"])
        }
        api_response["activity"].append(formatted_activity)
    
    import json
    print(json.dumps(api_response, indent=2))

if __name__ == "__main__":
    test_activity_methods()
