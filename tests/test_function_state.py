import pytest
import asyncio

from src.core.email_librarian_server.api_router import APIRouter


class FakeStorage:
    def __init__(self):
        self._store = {}
        class DB:
            async def fetch_all(self, q):
                return []
        self.database = DB()

    async def get_function_state(self, name):
        return self._store.get(name)

    async def set_function_state(self, name, enabled):
        self._store[name] = bool(enabled)
        return True


class FakeServer:
    def __init__(self):
        self.storage_manager = FakeStorage()
        self.job_manager = type("J", (), {"active_jobs": []})
        self.organizer_factory = type("O", (), {"organizers_available": False})


@pytest.mark.asyncio
async def test_toggle_persists_and_returns_state():
    server = FakeServer()
    api = APIRouter(server)

    # toggle on
    res = await api.toggle_function("cataloging", {"enabled": True})
    assert res["function"] == "cataloging"
    assert res["enabled"] is True

    # persisted
    persisted = await server.storage_manager.get_function_state("cataloging")
    assert persisted is True

    # toggle off
    res2 = await api.toggle_function("cataloging", {"enabled": False})
    assert res2["enabled"] is False
    persisted2 = await server.storage_manager.get_function_state("cataloging")
    assert persisted2 is False


@pytest.mark.asyncio
async def test_get_function_status_uses_db_then_fallback():
    server = FakeServer()
    # ensure DB has no entry
    state = await server.storage_manager.get_function_state("shelving")
    assert state is None

    api = APIRouter(server)
    # fallback value from in-memory defaults should be False
    status = await api.get_function_status("shelving")
    assert status["function"] == "shelving"
    assert status["enabled"] is False

    # now persist True and read again
    await server.storage_manager.set_function_state("shelving", True)
    status2 = await api.get_function_status("shelving")
    assert status2["enabled"] is True
