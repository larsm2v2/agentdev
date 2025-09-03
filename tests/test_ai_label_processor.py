"""
Test script for the AI Label Assignment processor.

This script demonstrates how to use the AILabelAssignmentProcessor to assign labels to emails using AI.
"""

import asyncio
import uuid
import logging
import os
from typing import Dict, List, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ai_label_test")

# Import the required modules
from core.email_librarian_server.job_processors.ai_label_processor import AILabelAssignmentProcessor

class MockJobManager:
    """Mock job manager for testing."""
    
    def __init__(self):
        """Initialize with empty jobs dictionary."""
        self.jobs = {}
        
    async def update_job_status(self, job_id, status, results=None, error_message=None):
        """Update job status."""
        if job_id not in self.jobs:
            self.jobs[job_id] = {}
            
        self.jobs[job_id].update({
            'status': status,
            'results': results,
            'error_message': error_message
        })
        
        logger.info(f"Job {job_id} status updated to {status}")
        if error_message:
            logger.info(f"Job {job_id} error: {error_message}")
        if results and isinstance(results, dict):
            logger.info(f"Job {job_id} message: {results.get('message', '')}")
            
        return self.jobs[job_id]

class MockOrganizer:
    """Mock Gmail organizer for testing."""
    
    def __init__(self):
        """Initialize with mock data."""
        self.emails = {
            f"msg_{i}": {
                "message_id": f"msg_{i}",
                "sender": f"user{i}@example.com",
                "subject": f"Test Email {i} about {'work' if i % 3 == 0 else 'personal' if i % 3 == 1 else 'shopping'} topic",
                "raw_body": f"This is test email {i} content about {'work-related issues' if i % 3 == 0 else 'personal matters' if i % 3 == 1 else 'online shopping receipts'}."
            } for i in range(1, 11)
        }
        
        self.labels = {
            "Work": {"id": "Label_1", "name": "Work"},
            "Personal": {"id": "Label_2", "name": "Personal"},
            "Shopping": {"id": "Label_3", "name": "Shopping"}
        }
    
    async def fetch_email(self, message_id):
        """Mock fetching an email."""
        if message_id in self.emails:
            return self.emails[message_id]
        return {"message_id": message_id, "error": "Email not found"}
    
    def suggest_category(self, subject, sender, body):
        """Mock AI categorization."""
        # Simple rule-based mock for testing
        if "work" in subject.lower() or "work" in body.lower():
            return {"category": "Work", "confidence": 0.9}
        elif "personal" in subject.lower() or "personal" in body.lower():
            return {"category": "Personal", "confidence": 0.8}
        elif "shopping" in subject.lower() or "shopping" in body.lower():
            return {"category": "Shopping", "confidence": 0.7}
        return {"category": "Other", "confidence": 0.5}
    
    def create_label(self, label_name):
        """Mock creating a label."""
        if label_name in self.labels:
            return {"status": "success", "label": self.labels[label_name]}
        
        # Create new label
        new_label = {"id": f"Label_{len(self.labels) + 1}", "name": label_name}
        self.labels[label_name] = new_label
        return {"status": "success", "label": new_label}
    
    def apply_label(self, message_id, label_id):
        """Mock applying a label to an email."""
        # Check if message exists
        if not any(e.get("message_id") == message_id for e in self.emails.values()):
            return None
            
        # Check if label exists
        label_exists = any(label.get("id") == label_id for label in self.labels.values())
        if not label_exists:
            return None
            
        return {"status": "success", "message_id": message_id, "label_id": label_id}

class MockOrganizerFactory:
    """Mock organizer factory for testing."""
    
    def create_organizer(self, organizer_type=None):
        """Create a mock organizer."""
        return MockOrganizer()

class MockStorageManager:
    """Mock storage manager for testing."""
    
    async def get_labels(self):
        """Mock getting labels."""
        return ["Work", "Personal", "Shopping", "Finance", "Travel", "Updates"]

async def run_test():
    """Run a test of the AILabelAssignmentProcessor."""
    # Create components
    job_manager = MockJobManager()
    organizer_factory = MockOrganizerFactory()
    storage_manager = MockStorageManager()
    
    # Create the processor
    label_processor = AILabelAssignmentProcessor(
        database=None,
        organizer_factory=organizer_factory,
        job_manager=job_manager,
        storage_manager=storage_manager
    )
    
    # Create test data
    job_id = str(uuid.uuid4())
    
    # Test with email data directly
    email_data = [
        {
            "message_id": "msg_direct_1",
            "subject": "Work project status",
            "from": "boss@example.com",
            "body": "Please provide an update on the project status."
        },
        {
            "message_id": "msg_direct_2",
            "subject": "Personal vacation plans",
            "from": "friend@example.com",
            "body": "Let's discuss our vacation plans for next month."
        }
    ]
    
    # Create job parameters - test with direct email data
    parameters_direct = {
        "emails": email_data,
        "custom_categories": ["Work", "Personal", "Shopping", "Other"],
        "apply_labels": True
    }
    
    logger.info("Starting AI label assignment job with direct email data...")
    
    # Process the direct email data job
    results_direct = await label_processor.process(job_id, parameters_direct)
    
    logger.info(f"Direct email job completed with status: {results_direct.get('status')}")
    
    # Test with message IDs
    message_ids = [f"msg_{i}" for i in range(1, 6)]  # 5 message IDs
    
    job_id_2 = str(uuid.uuid4())
    
    # Create job parameters - test with message IDs
    parameters_ids = {
        "message_ids": message_ids,
        "apply_labels": True,
        "batch_size": 2  # Small batch size for testing
    }
    
    logger.info("Starting AI label assignment job with message IDs...")
    
    # Process the message IDs job
    results_ids = await label_processor.process(job_id_2, parameters_ids)
    
    logger.info(f"Message IDs job completed with status: {results_ids.get('status')}")
    
    # Print results summary
    direct_emails = results_direct.get('emails', [])
    if direct_emails:
        logger.info("Direct email results:")
        for email in direct_emails:
            logger.info(f"  - {email.get('message_id')}: {email.get('assigned_category')}")
    
    id_emails = results_ids.get('emails', [])
    if id_emails:
        logger.info("Message ID results:")
        for email in id_emails:
            logger.info(f"  - {email.get('message_id')}: {email.get('assigned_category')}")
    
    return {
        "direct_results": results_direct,
        "id_results": results_ids
    }

if __name__ == "__main__":
    # Check if we have an OpenAI API key for testing with real AI
    if not os.environ.get("OPENAI_API_KEY"):
        logger.warning("No OpenAI API key found in environment. Using mock AI only.")
    
    asyncio.run(run_test())
