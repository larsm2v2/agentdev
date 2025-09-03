"""
Test script for the Message ID Retrieval job processor.

This script demonstrates how to use the MessageIDRetrievalProcessor to get message IDs in a date range.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("message_id_test")

# Import the required modules
from src.core.email_librarian_server.message_id_processor import MessageIDRetrievalProcessor
from src.core.email_librarian_server.organizer_factory import OrganizerFactory

class MockOrganizer:
    """Mock organizer for testing purposes."""
    
    def search_messages(self, query=None, max_results=10):
        """Return mock message IDs."""
        # Simulate retrieving message IDs from a date range
        logger.info(f"Searching messages with query: {query}, max_results: {max_results}")
        
        # Generate sample IDs
        sample_ids = [f"msg_{i}" for i in range(1, 21)]
        return sample_ids[:max_results]

class MockOrganizerFactory:
    """Mock organizer factory for testing."""
    
    def create_organizer(self, organizer_type=None):
        """Return a mock organizer."""
        return MockOrganizer()

class MockJobManager:
    """Mock job manager for testing."""
    
    async def update_job_status(self, job_id, status, message=None, metadata=None):
        """Log job status updates."""
        logger.info(f"Job {job_id}: Status={status}, Message={message}")
        if metadata:
            logger.info(f"Job {job_id}: Metadata={metadata}")

async def test_message_id_retrieval_job():
    """Test the message ID retrieval job."""
    # Create mock components
    organizer_factory = MockOrganizerFactory()
    job_manager = MockJobManager()
    
    # Create the job processor
    processor = MessageIDRetrievalProcessor(
        organizer_factory=organizer_factory,
        job_manager=job_manager
    )
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Create parameters for last 7 days
    today = datetime.now()
    start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    
    parameters = {
        "start_date": start_date,
        "end_date": end_date,
        "batch_size": 5,
        "max_ids": 10
    }
    
    # Run the job
    logger.info(f"Starting message ID retrieval job with parameters: {parameters}")
    result = await processor.process(job_id, parameters)
    
    # Show results
    logger.info(f"Job completed with status: {result.get('status')}")
    logger.info(f"Retrieved {result.get('message_count')} message IDs in {result.get('batch_count')} batches")
    
    # Display the batches
    if 'batches' in result:
        for i, batch in enumerate(result['batches']):
            logger.info(f"Batch {i+1}: {batch}")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_message_id_retrieval_job())
