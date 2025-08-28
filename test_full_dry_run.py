import asyncio
from pathlib import Path
from src.core.email_librarian_server.organizer_factory import OrganizerFactory
from src.core.email_librarian_server.job_processors import CatalogingJobProcessor, ShelvingJobProcessor

async def main():
    token_file = Path("data/gmail_token.pickle").resolve()
    real_factory = OrganizerFactory(credentials_path="config/credentials.json", token_path=str(token_file))

    # Create real organizers (authenticated)
    real_org_for_catalog = real_factory.create_organizer("high_performance")
    real_org_for_shelving = real_factory.create_organizer("high_performance")

    # Monkeypatch shelving organizer to avoid any mailbox modifications (dry run)
    def create_label_stub(label_name):
        print(f"[dry-run] create_label called for '{label_name}'")
        return {"status": "success", "label": {"id": f"dry-{label_name}"}}

    def apply_label_stub(msg_id, label_id):
        print(f"[dry-run] apply_label called for msg={msg_id} label={label_id}")
        return True

    # Attach stubs
    setattr(real_org_for_shelving, 'create_label', create_label_stub)
    setattr(real_org_for_shelving, 'apply_label', apply_label_stub)

    # Create simple factories that return prepared organizers
    class SimpleFactory:
        def __init__(self, org):
            self._org = org
        def create_organizer(self, organizer_type: str = "high_performance"):
            return self._org

    catalog_factory = SimpleFactory(real_org_for_catalog)
    shelving_factory = SimpleFactory(real_org_for_shelving)

    # Instantiate processors (no DB, no job_manager, no storage_manager) for a dry run
    catalog_proc = CatalogingJobProcessor(database=None, organizer_factory=catalog_factory, job_manager=None, storage_manager=None)
    shelving_proc = ShelvingJobProcessor(database=None, organizer_factory=shelving_factory, job_manager=None)

    # Parameters for Aug 25-26 inclusive
    params = {
        "date_range": {"start": "2025-08-25T00:00:00Z", "end": "2025-08-27T00:00:00Z"},
        "batch_size": 25,
    "concurrency": 2,
        "page_size": 500,
        "max_ids": 2000,
    "batch_pause_sec": 0.5,
    "batch_attempts": 5
    }

    print("Starting cataloging dry run...")
    try:
        catalog_res = await catalog_proc.process("dry-catalog", params)
        print("Cataloging result:\n", catalog_res)
    except Exception as e:
        print("Cataloging failed:", e)

    print("Starting shelving dry run...")
    try:
        shelving_res = await shelving_proc.process("dry-shelve", params)
        print("Shelving result:\n", shelving_res)
    except Exception as e:
        print("Shelving failed:", e)

if __name__ == '__main__':
    asyncio.run(main())
