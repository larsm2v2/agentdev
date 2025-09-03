from fastapi import FastAPI
from fastapi.testclient import TestClient
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
        self.job_manager = type("J", (), {"active_jobs": []})


def make_client_for_server(server):
    api = APIRouter(server)
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_http_get_labels_from_storage():
    storage = FakeStorageWithLabels(["Inbox", "Archive"])
    server = MinimalServer(storage_manager=storage)
    client = make_client_for_server(server)

    r = client.get("/api/labels")
    assert r.status_code == 200
    assert r.json() == ["Inbox", "Archive"]


def test_http_get_labels_from_organizer():
    storage = FakeStorageNoLabels()
    organizer_factory = FakeOrganizerFactory(available=True, labels=["Todo", "Later"])
    server = MinimalServer(storage_manager=storage, organizer_factory=organizer_factory)
    client = make_client_for_server(server)

    r = client.get("/api/labels")
    assert r.status_code == 200
    assert r.json() == ["Todo", "Later"]


def test_http_get_labels_empty():
    server = MinimalServer(storage_manager=None, organizer_factory=FakeOrganizerFactory(available=False))
    client = make_client_for_server(server)

    r = client.get("/api/labels")
    assert r.status_code == 200
    assert r.json() == []
