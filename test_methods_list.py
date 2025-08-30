import sys, os
sys.path.insert(0, os.getcwd())

from src.core.email_librarian_server.organizer_factory import OrganizerFactory
f = OrganizerFactory()
print("organizers_available:", f.organizers_available)
org = f.create_organizer()
org_class = getattr(org, "__class__", None)
print("organizer type:", type(org), "class:", org_class.__name__ if org_class is not None else "Unknown")

needed = [
    "authenticate", "list_labels", "get_message", "fetch_email", "list_message_ids",
    "fetch_email_batches", "classify_batch", "classify_batches", "apply_label", "apply_label_batches", "service"
]
for name in needed:
    print(name, "->", hasattr(org, name))
# Optional: call list_labels safely
try:
    labels = org.list_labels()
    print("list_labels() returned:", type(labels), (labels[:15] if isinstance(labels, list) else labels))
except Exception as e:
    print("list_labels() call error:", e)
