"""
Test script for the Email Batch Retrieval processor.

This script demonstrates how to use the EmailBatchRetrievalProcessor to retrieve
batches of emails with raw content and labels.
"""

import asyncio
import uuid
import logging
from typing import Dict, List, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("email_batch_test")

# Import the required modules
from core.email_librarian_server.job_processors.email_batch_processor import EmailBatchRetrievalProcessor

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
        if results:
            logger.info(f"Job {job_id} results: {results}")
            
        return self.jobs[job_id]

class MockOrganizer:
    """Mock Gmail organizer for testing."""
    
    def __init__(self):
        """Initialize with mock data."""
        self.emails = {
            f"msg_{i}": {
                "message_id": f"msg_{i}",
                "sender": f"user{i}@example.com",
                "subject": f"Test Email {i}",
                "raw": f"From: user{i}@example.com\nTo: recipient@example.com\nSubject: Test Email {i}\n\nThis is test email {i} content."
            } for i in range(1, 11)
        }
        
        self.labels = {
            f"msg_{i}": [f"Label{j}" for j in range(1, min(i+1, 4))]
            for i in range(1, 11)
        }
    
    async def fetch_email(self, message_id):
        """Mock fetching an email."""
        if message_id in self.emails:
            return self.emails[message_id]
        return {"message_id": message_id, "error": "Email not found"}
    
    async def get_message_labels(self, message_id):
        """Mock getting labels for an email."""
        if message_id in self.labels:
            return self.labels[message_id]
        return []

class MockOrganizerFactory:
    """Mock organizer factory for testing."""
    
    def create_organizer(self):
        """Create a mock organizer."""
        return MockOrganizer()

async def run_test():
    """Run a test of the EmailBatchRetrievalProcessor."""
    # Create components
    job_manager = MockJobManager()
    organizer_factory = MockOrganizerFactory()
    
    # Create the processor
    batch_processor = EmailBatchRetrievalProcessor(
        database=None,
        organizer_factory=organizer_factory,
        job_manager=job_manager
    )
    
    # Create test data
    job_id = str(uuid.uuid4())
    
    # Test with batches of message IDs
    batches = [
        [f"msg_{i}" for i in range(1, 6)],  # 5 messages in first batch
        [f"msg_{i}" for i in range(6, 11)]   # 5 messages in second batch
    ]
    
    # Create job parameters
    parameters = {
        "batches": batches,
        "include_labels": True,
        "chunk_size": 5
    }
    
    logger.info(f"Starting email batch retrieval job with parameters: {parameters}")
    
    # Process the job
    results = await batch_processor.process(job_id, parameters)
    
    logger.info(f"Job completed with status: {results.get('status')}")
    logger.info(f"Requested: {results.get('requested')}, Returned: {results.get('returned')}")
    
    # Print summary of each batch
    for i, batch in enumerate(results.get('batches', [])):
        logger.info(f"Batch {i+1} contains {len(batch)} emails")
        # Print first email in batch as example
        if batch:
            logger.info(f"Sample email: {batch[0].get('message_id')} - {batch[0].get('subject')}")
            logger.info(f"Labels: {batch[0].get('labels')}")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_test())
