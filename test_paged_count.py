import asyncio
from pathlib import Path
from src.core.email_librarian_server.organizer_factory import OrganizerFactory

async def main():
    token_file = Path("data/gmail_token.pickle").resolve()
    factory = OrganizerFactory(credentials_path="config/credentials.json", token_path=str(token_file))
    org = factory.create_organizer("high_performance")
    ok = org.authenticate()
    print("Auth result:", ok)
    if not ok:
        print("Auth failed")
        return
    service = org.service
    # Query covering Aug 25-26
    query = "after:2025/08/24 before:2025/08/27"
    max_ids = 10000
    page_size = 500

    api_calls = 0
    ids = []

    def list_page(page_token=None):
        nonlocal api_calls
        api_calls += 1
        if page_token:
            resp = service.users().messages().list(userId='me', q=query, maxResults=page_size, pageToken=page_token).execute()
        else:
            resp = service.users().messages().list(userId='me', q=query, maxResults=page_size).execute()
        return resp

    page_token = None
    while True:
        try:
            res = await asyncio.to_thread(list_page, page_token)
        except Exception as e:
            print('List failed:', e)
            break
        msgs = res.get('messages') or []
        ids.extend([m.get('id') for m in msgs if m.get('id')])
        if len(ids) >= max_ids:
            ids = ids[:max_ids]
            break
        page_token = res.get('nextPageToken')
        if not page_token:
            break

    print('Total message ids collected:', len(ids))
    print('messages.list API calls made:', api_calls)
    if len(ids) > 0:
        print('Sample ids:', ids[:20])

if __name__ == '__main__':
    asyncio.run(main())
