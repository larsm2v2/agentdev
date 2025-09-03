"""
Test script for the GmailLabelProcessor.

This script verifies the Gmail Label Processor functionality.
"""

import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock

from core.email_librarian_server.job_processors.gmail_label_processor import GmailLabelProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockOrganizer:
    """Mock organizer for testing."""
    
    def __init__(self):
        """Initialize with mock methods."""
        self.labels_created = {}
        self.labels_applied = {}
    
    def create_label(self, label_name):
        """Create a label and return success response."""
        if label_name in self.labels_created:
            label_id = self.labels_created[label_name]
        else:
            # Generate a mock label ID
            label_id = f"label_{label_name.replace(' ', '_').lower()}"
            self.labels_created[label_name] = label_id
        
        return {
            "status": "success",
            "label": {
                "id": label_id,
                "name": label_name
            }
        }
    
    def apply_label(self, email_id, label_id):
        """Apply a label to an email and return success."""
        if email_id not in self.labels_applied:
            self.labels_applied[email_id] = []
        
        self.labels_applied[email_id].append(label_id)
        return True


class MockOrganizerFactory:
    """Mock organizer factory for testing."""
    
    def __init__(self):
        """Initialize with mock organizer."""
        self.organizer = MockOrganizer()
    
    def create_organizer(self, organizer_type=None):
        """Return the mock organizer."""
        return self.organizer


async def test_gmail_label_processor():
    """Test the GmailLabelProcessor."""
    logger.info("Starting GmailLabelProcessor test...")
    
    # Create mock components
    mock_db = AsyncMock()
    mock_job_manager = AsyncMock()
    mock_storage_manager = AsyncMock()
    mock_organizer_factory = MockOrganizerFactory()
    
    # Create the processor
    processor = GmailLabelProcessor(
        database=mock_db,
        organizer_factory=mock_organizer_factory,
        job_manager=mock_job_manager,
        storage_manager=mock_storage_manager
    )
    
    # Test 1: Apply a single label to multiple messages
    logger.info("Test 1: Applying a single label to multiple messages...")
    
    message_ids = ["msg_1", "msg_2", "msg_3"]
    default_label = "Important"
    
    job_id = "test_job_1"
    parameters = {
        "message_ids": message_ids,
        "default_label": default_label
    }
    
    # Process the job
    results = await processor.process(job_id, parameters)
    
    # Verify results
    logger.info(f"Job results: {results}")
    assert results["labeled_count"] == len(message_ids), "All messages should be labeled"
    
    # Verify labels were applied
    organizer = mock_organizer_factory.organizer
    for msg_id in message_ids:
        assert msg_id in organizer.labels_applied, f"Label should be applied to {msg_id}"
    
    # Test 2: Apply different labels based on mapping
    logger.info("Test 2: Applying different labels based on mapping...")
    
    message_ids = ["msg_4", "msg_5", "msg_6"]
    label_mapping = {
        "msg_4": "Work",
        "msg_5": "Personal",
        "msg_6": "Shopping"
    }
    
    job_id = "test_job_2"
    parameters = {
        "message_ids": message_ids,
        "label_mapping": label_mapping
    }
    
    # Process the job
    results = await processor.process(job_id, parameters)
    
    # Verify results
    logger.info(f"Job results: {results}")
    assert results["labeled_count"] == len(message_ids), "All messages should be labeled"
    
    # Verify correct labels were created
    for label in label_mapping.values():
        assert label in organizer.labels_created, f"Label '{label}' should be created"
    
    # Test 3: Process emails with mixed label mapping
    logger.info("Test 3: Processing emails with mixed label mapping...")
    
    message_ids = ["email_1", "email_2", "email_3"]
    label_mapping = {
        "email_1": "Work",
        "email_3": "Personal"
    }
    default_label = "Other"
    
    job_id = "test_job_3"
    parameters = {
        "message_ids": message_ids,
        "label_mapping": label_mapping,
        "default_label": default_label
    }
    
    # Process the job
    results = await processor.process(job_id, parameters)
    
    # Verify results
    logger.info(f"Job results: {results}")
    assert results["labeled_count"] == len(message_ids), "All messages should be labeled"
    
    logger.info("All tests passed successfully!")
    return True


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_gmail_label_processor())
