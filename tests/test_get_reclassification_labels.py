import asyncio

from src.core.email_librarian_server.api_router import APIRouter


def test_get_labels_returns_non_empty():
    """Ensure get_labels returns a non-empty list when storage provides labels."""

    class FakeStorage:
        async def get_labels(self):
            # Return a realistic non-empty list of label dicts
            return [{"id": "LABEL_1", "name": "Inbox"}, {"id": "LABEL_2", "name": "Work"}]

    class FakeOrganizerFactory:
        organizers_available = False

    class FakeServer:
        def __init__(self):
            self.storage_manager = FakeStorage()
            self.organizer_factory = FakeOrganizerFactory()

    server = FakeServer()
    router = APIRouter(server)

    labels = asyncio.run(router.get_labels())

    assert isinstance(labels, list)
    assert len(labels) > 0
