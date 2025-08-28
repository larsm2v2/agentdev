import sys
sys.path.insert(0, r'c:/Users/Lawrence/Documents/GitHub/agentdev')
try:
    import src.gmail.gmail_organizer as go
    import src.core.email_librarian_server.job_processors as jp
    print('IMPORT_OK')
    # Check for instance attribute by creating an instance safely (no network calls)
    inst = go.GmailAIOrganizer()
    print('instance_has_rate_limiter:', hasattr(inst, 'rate_limiter'))
except Exception as e:
    print('IMPORT_FAIL', e)
    raise
