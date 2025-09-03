import asyncio
from pathlib import Path
from src.core.email_librarian_server.organizer_factory import OrganizerFactory

async def main():
    token_file = Path("data/gmail_token.pickle").resolve()
    factory = OrganizerFactory(credentials_path="config/credentials.json", token_path=str(token_file))
    org = factory.create_organizer("high_performance")
    # ensure authenticated
    ok = org.authenticate()
    print("Auth result:", ok)
    if not ok:
        print("Auth failed")
        return
    loop = asyncio.get_event_loop()
    service = org.service
    # build query for date range to cover Aug 25 and Aug 26 inclusive
    q = "after:2025/08/24 before:2025/08/27"
    print("Using query:", q)
    def list_call():
        req = service.users().messages().list(userId="me", q=q, maxResults=200)
        return req.execute()
    try:
        res = await asyncio.to_thread(list_call)
        msgs = res.get("messages", []) or []
        print("Found message ids (first page):", [m["id"] for m in msgs[:50]])
        print("Total listed on first page:", len(msgs))
        # print nextPageToken presence
        print("nextPageToken:", res.get("nextPageToken"))
    except Exception as e:
        print("Gmail list failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
