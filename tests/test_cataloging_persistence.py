import asyncio
import pytest
import uuid
from core.email_librarian_server.job_processors.job_processors import CatalogingJobProcessor


class FakeStorage:
    def __init__(self):
        self.stored_metadata = []
        self.stored_vectors = []

    async def store_email_metadata(self, email_data):
        self.stored_metadata.append(email_data)
        return True

    async def store_email_vector(self, email_id, vector, metadata):
        self.stored_vectors.append((email_id, vector, metadata))
        return True


from core.email_librarian_server.organizer_factory import OrganizerFactory

class FakeOrganizerFactory(OrganizerFactory):
    def create_organizer(self, organizer_type: str = "high_performance", server=None, config=None):
        class O:
            async def search_emails(self, query=None, max_results=10):
                return [
                    {"id": "e1", "subject": "Invoice 123", "from": "billing@example.com", "snippet": "Your invoice"},
                    {"id": "e2", "subject": "Meeting notes", "from": "teammate@work.com", "snippet": "Notes"}
                ]
        return O()


@pytest.mark.asyncio
async def test_cataloging_persists_metadata_and_vectors():
    storage = FakeStorage()
    factory = FakeOrganizerFactory()

    processor = CatalogingJobProcessor(database=None, organizer_factory=factory, job_manager=None, storage_manager=storage)

    job_id = str(uuid.uuid4())
    result = await processor.process(job_id, {"batch_size": 2})

    assert isinstance(result, dict)
    # Ensure metadata persisted for both emails
    assert len(storage.stored_metadata) >= 2
    # Ensure vectors stored
    assert len(storage.stored_vectors) >= 2


if __name__ == '__main__':
    asyncio.run(test_cataloging_persists_metadata_and_vectors())
