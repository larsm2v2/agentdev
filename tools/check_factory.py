import sys
from pprint import pprint

# ensure repo root on sys.path
sys.path.insert(0, '.')

from src.core.email_librarian_server.organizer_factory import OrganizerFactory

of = OrganizerFactory()
print('organizers_available =', of.organizers_available)
print('high_performance_organizer =', of.high_performance_organizer)
print('standard_organizer =', of.standard_organizer)

org = of.create_organizer()
print('created organizer type:', type(org))
attrs = ['list_labels', 'list_message_ids', 'fetch_email', 'fetch_email_batches', 'classify_batch', 'apply_label']
for a in attrs:
    print(f"has {a}:", hasattr(org, a))

# try calling list_labels safely
if hasattr(org, 'list_labels'):
    try:
        lbls = org.list_labels()
        print('list_labels() returned type:', type(lbls))
        if isinstance(lbls, list):
            print('first 5 labels:', lbls[:5])
    except Exception as e:
        print('list_labels() raised:', e)
else:
    print('organizer has no list_labels method')
