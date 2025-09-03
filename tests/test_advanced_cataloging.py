"""
Test script for the Advanced Cataloging pipeline.

This script verifies the advanced cataloging pipeline functionality
which uses the processor pipeline.
"""

import asyncio
import logging
import json
from unittest.mock import MagicMock, AsyncMock
import uuid

from fastapi import BackgroundTasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the advanced cataloging module
from src.core.email_librarian_server.advanced_cataloging import start_advanced_cataloging, process_advanced_cataloging

class MockJobManager:
    """Mock job manager for testing."""
    
    def __init__(self):
        """Initialize with active jobs."""
        self.active_jobs = {}
        self.processors = {}
        self.next_job_id = 1
    
    async def create_job(self, job_config):
        """Create a job and return its ID."""
        job_id = f"test_job_{self.next_job_id}"
        self.next_job_id += 1
        
        self.active_jobs[job_id] = {
            "job_id": job_id,
            "id": job_id,
            "status": "pending",
            "job_type": job_config.get("job_type", "unknown"),
            "parameters": job_config.get("parameters", {})
        }
        
        # Process the job based on type
        job_type = job_config.get("job_type")
        if job_type in self.processors:
            processor = self.processors[job_type]
            # Simulate processing
            result = await processor.process(job_id, job_config.get("parameters", {}))
            self.active_jobs[job_id]["status"] = "completed"
            self.active_jobs[job_id].update(result)
        
        return {"id": job_id, "job_id": job_id}
    
    async def get_job_status(self, job_id):
        """Get job status."""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        return {"status": "not_found"}
    
    def register_processor(self, job_type, processor):
        """Register a processor for a job type."""
        self.processors[job_type] = processor
        

class MockAPIRouter:
    """Mock API router for testing."""
    
    def __init__(self):
        """Initialize with mock server."""
        self.server = MagicMock()
        self.server.job_manager = MockJobManager()
        
        
class MockProcessor:
    """Mock processor for testing."""
    
    def __init__(self, result=None):
        """Initialize with a result."""
        self.result = result or {}
        
    async def process(self, job_id, parameters):
        """Process a job and return the result."""
        await asyncio.sleep(0.1)  # Simulate processing
        return self.result


async def test_advanced_cataloging():
    """Test the advanced cataloging pipeline."""
    logger.info("Starting advanced cataloging test...")
    
    # Create mock API router
    api_router = MockAPIRouter()
    
    # Create mock background tasks
    background_tasks = BackgroundTasks()
    
    # Create mock processors
    message_id_processor = MockProcessor({
        "message_ids": [f"msg_{i}" for i in range(1, 11)],
        "status": "completed"
    })
    
    batch_processor = MockProcessor({
        "batches": [["msg_1", "msg_2", "msg_3"], ["msg_4", "msg_5", "msg_6"], ["msg_7", "msg_8", "msg_9", "msg_10"]],
        "status": "completed"
    })
    
    email_batch_processor = MockProcessor({
        "emails": [
            {"id": "msg_1", "subject": "Test 1"},
            {"id": "msg_2", "subject": "Test 2"},
            {"id": "msg_3", "subject": "Test 3"}
        ],
        "status": "completed"
    })
    
    ai_label_processor = MockProcessor({
        "emails": [
            {"id": "msg_1", "subject": "Test 1", "assigned_category": "Work"},
            {"id": "msg_2", "subject": "Test 2", "assigned_category": "Personal"},
            {"id": "msg_3", "subject": "Test 3", "assigned_category": "Shopping"}
        ],
        "status": "completed"
    })
    
    gmail_label_processor = MockProcessor({
        "labeled_count": 3,
        "status": "completed"
    })
    
    # Register processors with job manager
    job_manager = api_router.server.job_manager
    job_manager.register_processor("message_id_retrieval", message_id_processor)
    job_manager.register_processor("message_id_batch", batch_processor)
    job_manager.register_processor("email_batch_retrieval", email_batch_processor)
    job_manager.register_processor("ai_label_assignment", ai_label_processor)
    job_manager.register_processor("gmail_label_application", gmail_label_processor)
    
    # Define test parameters
    parameters = {
        "start_date": "2025-01-01",
        "end_date": "2025-09-01",
        "batch_size": 3,
        "apply_labels": True
    }
    
    # Start the advanced cataloging process
    result = await start_advanced_cataloging(api_router, background_tasks, parameters)
    
    logger.info(f"Advanced cataloging started with result: {result}")
    
    # Get the master job ID
    master_job_id = result.get("job_id")
    
    if not master_job_id:
        logger.error("No master job ID returned")
        return False
    
    # Run the background task directly (normally this would happen in the background)
    await process_advanced_cataloging(api_router, master_job_id, parameters, background_tasks)
    
    # Check the status of the master job
    master_job = job_manager.active_jobs.get(master_job_id)
    logger.info(f"Master job status: {master_job.get('status')}")
    logger.info(f"Sub-jobs: {len(master_job.get('sub_jobs', []))}")
    
    # Log details about the sub-jobs
    for sub_job in master_job.get("sub_jobs", []):
        sub_job_id = sub_job.get("job_id")
        sub_job_status = job_manager.active_jobs.get(sub_job_id, {}).get("status")
        sub_job_type = sub_job.get("job_type")
        logger.info(f"Sub-job {sub_job_id} ({sub_job_type}): {sub_job_status}")
    
    # Verify the master job completed successfully
    assert master_job.get("status") == "completed", "Master job should be completed"
    
    # Verify the total processed count
    processed_count = master_job.get("processed_count", 0)
    assert processed_count > 0, "Should have processed some messages"
    
    logger.info("Advanced cataloging test completed successfully!")
    return True


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_advanced_cataloging())
