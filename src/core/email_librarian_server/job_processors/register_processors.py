"""
Registration script for Message ID job processors, Email Batch Retrieval, AI Label Assignment,
and Gmail Label application.

This script shows how to register MessageIDRetrievalProcessor, MessageIDBatchProcessor,
EmailBatchRetrievalProcessor, AILabelAssignmentProcessor, and GmailLabelProcessor with the job manager.
"""

from .message_id_processor import MessageIDRetrievalProcessor
from .message_id_batch_processor import MessageIDBatchProcessor
from .email_batch_processor import EmailBatchRetrievalProcessor
from .ai_label_processor import AILabelAssignmentProcessor
from .gmail_label_processor import GmailLabelProcessor

def register_message_id_processor(job_manager, database=None, organizer_factory=None, storage_manager=None):
    """
    Register the Message ID Retrieval processor with the job manager.
    
    Args:
        job_manager: The job manager instance
        database: Optional database connection
        organizer_factory: Optional organizer factory
        storage_manager: Optional storage manager
    
    Returns:
        The registered processor instance
    """
    # If a storage manager is provided and no explicit database was passed,
    # use the storage manager's database connection so processors persist to Postgres.
    if database is None and storage_manager is not None:
        database = getattr(storage_manager, "database", None)

    # Create the processor
    processor = MessageIDRetrievalProcessor(
        database=database,
        organizer_factory=organizer_factory,
        job_manager=job_manager,
        storage_manager=storage_manager
    )
    
    # Register with the job manager
    job_manager.register_processor("message_id_retrieval", processor)
    
    return processor

def register_message_id_batch_processor(job_manager, database=None, organizer_factory=None, storage_manager=None):
    """
    Register the Message ID Batch processor with the job manager.
    
    Args:
        job_manager: The job manager instance
        database: Optional database connection
        organizer_factory: Optional organizer factory
        storage_manager: Optional storage manager
    
    Returns:
        The registered processor instance
    """
    if database is None and storage_manager is not None:
        database = getattr(storage_manager, "database", None)

    # Create the processor
    processor = MessageIDBatchProcessor(
        database=database,
        organizer_factory=organizer_factory,
        job_manager=job_manager,
        storage_manager=storage_manager
    )
    
    # Register with the job manager
    job_manager.register_processor("message_id_batch", processor)
    
    return processor

def register_email_batch_processor(job_manager, database=None, organizer_factory=None, storage_manager=None):
    """
    Register the Email Batch Retrieval processor with the job manager.
    
    Args:
        job_manager: The job manager instance
        database: Optional database connection
        organizer_factory: Optional organizer factory
        storage_manager: Optional storage manager
    
    Returns:
        The registered processor instance
    """
    if database is None and storage_manager is not None:
        database = getattr(storage_manager, "database", None)

    # Create the processor
    processor = EmailBatchRetrievalProcessor(
        database=database,
        organizer_factory=organizer_factory,
        job_manager=job_manager,
        storage_manager=storage_manager
    )
    
    # Register with the job manager
    job_manager.register_processor("email_batch_retrieval", processor)
    
    return processor
    
def register_ai_label_processor(job_manager, database=None, organizer_factory=None, storage_manager=None):
    """
    Register the AI Label Assignment processor with the job manager.
    
    Args:
        job_manager: The job manager instance
        database: Optional database connection
        organizer_factory: Optional organizer factory
        storage_manager: Optional storage manager
    
    Returns:
        The registered processor instance
    """
    if database is None and storage_manager is not None:
        database = getattr(storage_manager, "database", None)

    # Create the processor
    processor = AILabelAssignmentProcessor(
        database=database,
        organizer_factory=organizer_factory,
        job_manager=job_manager,
        storage_manager=storage_manager
    )
    
    # Register with the job manager
    job_manager.register_processor("ai_label_assignment", processor)
    
    return processor

def register_gmail_label_processor(job_manager, database=None, organizer_factory=None, storage_manager=None):
    """
    Register the Gmail Label Processor with the job manager.
    
    Args:
        job_manager: The job manager instance
        database: Optional database connection
        organizer_factory: Optional organizer factory
        storage_manager: Optional storage manager
    
    Returns:
        The registered processor instance
    """
    if database is None and storage_manager is not None:
        database = getattr(storage_manager, "database", None)

    # Create the processor
    processor = GmailLabelProcessor(
        database=database,
        organizer_factory=organizer_factory,
        job_manager=job_manager,
        storage_manager=storage_manager
    )
    
    # Register with the job manager
    job_manager.register_processor("gmail_label_application", processor)
    
    return processor

# Example of how to use this in the server startup code:
"""
async def setup_processors(self):
    # Setup job processors
    from .job_processors import ShelvingJobProcessor, CatalogingJobProcessor
    from .message_id_processor import register_message_id_processor
    
    # Register existing processors
    self.job_manager.register_processor(
        "shelving", 
        ShelvingJobProcessor(
            database=self.storage_manager.database, 
            organizer_factory=self.organizer_factory, 
            job_manager=self.job_manager,
            storage_manager=self.storage_manager
        )
    )
    
    self.job_manager.register_processor(
        "cataloging", 
        CatalogingJobProcessor(
            database=self.storage_manager.database, 
            organizer_factory=self.organizer_factory,
            job_manager=self.job_manager,
            storage_manager=self.storage_manager
        )
    )
    
    # Register our message ID processors
    register_message_id_processor(
        self.job_manager,
        database=self.storage_manager.database,
        organizer_factory=self.organizer_factory,
        storage_manager=self.storage_manager
    )
    
    # Register the message ID batch processor
    register_message_id_batch_processor(
        self.job_manager,
        database=self.storage_manager.database,
        organizer_factory=self.organizer_factory,
        storage_manager=self.storage_manager
    )
    
    # Register the email batch retrieval processor
    register_email_batch_processor(
        self.job_manager,
        database=self.storage_manager.database,
        organizer_factory=self.organizer_factory,
        storage_manager=self.storage_manager
    )
    
    # Register the AI label assignment processor
    register_ai_label_processor(
        self.job_manager,
        database=self.storage_manager.database,
        organizer_factory=self.organizer_factory,
        storage_manager=self.storage_manager
    )
    
    # Register the Gmail label application processor
    register_gmail_label_processor(
        self.job_manager,
        database=self.storage_manager.database,
        organizer_factory=self.organizer_factory,
        storage_manager=self.storage_manager
    )
"""
