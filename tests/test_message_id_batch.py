"""
Test script for the Message ID Batch processor.

This script demonstrates how to use the MessageIDBatchProcessor to batch message IDs.
"""

import asyncio
import uuid
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("message_id_batch_test")

# Import the required modules
from src.core.email_librarian_server.job_processors.message_id_batch_processor import MessageIDBatchProcessor
from src.core.email_librarian_server.organizer_factory import OrganizerFactory
from src.core.email_librarian_server.job_processors.message_id_processor import EmailJobProcessor

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

class MockOrganizerFactory:
    """Mock organizer factory for testing."""
    
    def create_organizer(self):
        """Create a mock organizer."""
        class MockOrganizer:
            def __init__(self):
                pass
        return MockOrganizer()

async def run_test():
    """Run a test of the MessageIDBatchProcessor."""
    # Create components
    job_manager = MockJobManager()
    organizer_factory = MockOrganizerFactory()
    
    # Create the processor
    batch_processor = MessageIDBatchProcessor(
        database=None,
        organizer_factory=organizer_factory,
        job_manager=job_manager
    )
    
    # Create test data
    job_id = str(uuid.uuid4())
    message_ids = [f"msg_{i}" for i in range(1, 21)]  # 20 message IDs
    
    # Create job parameters
    parameters = {
        "message_ids": message_ids,
        "batch_size": 5
    }
    
    logger.info(f"Starting message ID batch job with parameters: {parameters}")
    
    # Process the job
    results = await batch_processor.process(job_id, parameters)
    
    logger.info(f"Job completed with status: {results.get('status')}")
    logger.info(f"Batches: {results.get('batches')}")
    logger.info(f"Total batches: {results.get('batch_count')}")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_test())
