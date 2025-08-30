import pytest

from src.core.email_librarian_server.api_router import APIRouter


class FakeStorageWithLabels:
    def __init__(self, labels):
        self._labels = labels

    async def get_labels(self):
        return list(self._labels)


class FakeStorageNoLabels:
    def __init__(self):
        pass


class FakeOrganizer:
    def __init__(self, labels=None):
        self._labels = labels or []

    def list_labels(self):
        # APIRouter calls this synchronously
        return list(self._labels)


class FakeOrganizerFactory:
    def __init__(self, available=False, labels=None):
        self.organizers_available = available
        self._labels = labels or []

    def create_organizer(self):
        return FakeOrganizer(self._labels)


class MinimalServer:
    def __init__(self, storage_manager=None, organizer_factory=None):
        self.storage_manager = storage_manager
        self.organizer_factory = organizer_factory or FakeOrganizerFactory()
        # minimal attributes referenced by APIRouter
        self.job_manager = type("J", (), {"active_jobs": []})


@pytest.mark.asyncio
async def test_get_labels_from_storage():
    storage = FakeStorageWithLabels(["Important", "Work"])
    server = MinimalServer(storage_manager=storage)
    api = APIRouter(server)

    labels = await api.get_labels()
    assert isinstance(labels, list)
    assert labels == ["Important", "Work"]


@pytest.mark.asyncio
async def test_get_labels_from_organizer():
    storage = FakeStorageNoLabels()
    organizer_factory = FakeOrganizerFactory(available=True, labels=["Personal", "Archive"])
    server = MinimalServer(storage_manager=storage, organizer_factory=organizer_factory)
    api = APIRouter(server)

    labels = await api.get_labels()
    assert isinstance(labels, list)
    assert labels == ["Personal", "Archive"]


@pytest.mark.asyncio
async def test_get_labels_empty_on_failure():
    # No storage manager and organizer unavailable -> should return empty list
    server = MinimalServer(storage_manager=None, organizer_factory=FakeOrganizerFactory(available=False))
    api = APIRouter(server)

    labels = await api.get_labels()
    assert isinstance(labels, list)
    assert labels == []
