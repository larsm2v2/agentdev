import asyncio
import pytest
import uuid
from src.core.email_librarian_server.job_manager import JobManager
from core.email_librarian_server.job_processors.job_processors import CatalogingJobProcessor
from src.core.email_librarian_server.organizer_factory import OrganizerStub, OrganizerFactory


from src.core.email_librarian_server.storage_manager import StorageManager

class DummyStorage(StorageManager):
    def __init__(self):
        super().__init__()
        self.database = None


class MockOrganizerFactory(OrganizerFactory):
    def __init__(self):
        self.container_gmail_available = False

    def create_organizer(self, organizer_type: str = "high_performance", server=None):
        class M:
            async def search_emails(self, query=None, max_results=10):
                return [
                    {"id": "email1", "subject": "Invoice for August", "from": "billing@example.com", "snippet": "Your invoice is attached."},
                    {"id": "email2", "subject": "Team meeting", "from": "colleague@work.com", "snippet": "Let's meet tomorrow."}
                ]
        return M()


@pytest.mark.asyncio
async def test_cataloging_processor_runs():
    storage = DummyStorage()
    organizer_factory = MockOrganizerFactory()
    jm = JobManager(storage_manager=storage, organizer_factory=organizer_factory)

    processor = CatalogingJobProcessor(database=None, organizer_factory=organizer_factory, job_manager=jm)
    jm.register_processor("cataloging", processor)

    job_config = {"job_type": "cataloging", "parameters": {"batch_size": 2}}
    # Directly call process_job to avoid background tasks complexity
    job_id = str(uuid.uuid4())
    result = await jm.process_job(job_id, job_config)

    assert isinstance(result, dict)
    assert result.get("job_type") == "cataloging"
    assert result.get("processed_count", 0) >= 0


if __name__ == '__main__':
    asyncio.run(test_cataloging_processor_runs())
