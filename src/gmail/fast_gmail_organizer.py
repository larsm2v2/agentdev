#!/usr/bin/env python3
"""
Async High-Performance Gmail Organizer

Features:
- Sequential Gmail API calls (SSL-safe) via asyncio.to_thread
- Concurrent LLM classification using asyncio.gather
- Smart content extraction
- Persistent classification cache
- Batch processing with hybrid approach
- Default fallback classification for robustness
"""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from gmail_organizer import GmailAIOrganizer


class AsyncHighPerformanceGmailOrganizer(GmailAIOrganizer):
    """Async high-performance Gmail organizer with caching and batch LLM classification"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        print("🔐 Authenticating Gmail service...")
        if not self.authenticate() or self.service is None:
            raise RuntimeError("Gmail service authentication failed")
        print("✅ Gmail service authenticated")

        self._gmail_lock = asyncio.Lock()
        self.cache_dir = Path("email_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.performance_stats = {
            "emails_processed": 0,
            "cache_hits": 0,
            "processing_time": 0
        }
    def list_labels(self) -> List[Dict[str, str]]:
        """List Gmail labels for the authenticated user.

        Returns a list of dicts with at least `id` and `name` keys. Returns an
        empty list if the service is not authenticated or on any error so the
        caller can continue without raising.
        """
        if not self.service:
            # Try to authenticate if possible
            try:
                authenticated = self.authenticate()
            except Exception:
                authenticated = False

            if not authenticated or not self.service:
                print("❌ Gmail service not authenticated - cannot list labels")
                return []

        try:
            resp = self.service.users().labels().list(userId='me').execute()
            labels = resp.get('labels', []) if isinstance(resp, dict) else []
            result = []
            for l in labels:
                # Normalize to id/name
                result.append({
                    'id': l.get('id'),
                    'name': l.get('name'),
                    'type': l.get('type') if 'type' in l else None
                })
            return result
        except Exception as e:
            print(f"❌ Error listing Gmail labels: {e}")
            return []

    # ----------------- Gmail fetch -----------------
    async def fetch_email(self, email_id: str) -> Dict[str, Any]:
        """Fetch single email safely using Gmail API (thread-safe)"""
        async with self._gmail_lock:
            return await asyncio.to_thread(self.get_email_content, email_id)

    async def fetch_email_batches(self, email_ids: List[str], batch_size: int = 10) -> List[List[Dict[str, Any]]]:
        """Fetch emails in sequential batches for SSL safety"""
        batches = [email_ids[i:i + batch_size] for i in range(0, len(email_ids), batch_size)]
        results: List[List[Dict[str, Any]]] = []

        for batch in batches:
            emails = []
            for email_id in batch:
                try:
                    email = await self.fetch_email(email_id)
                    emails.append(email)
                except Exception:
                    emails.append({"id": email_id, "fetched": False})
            results.append(emails)
        return results

    # ----------------- Content extraction -----------------
    def _extract_key_content(self, body: str, max_chars: int = 200) -> str:
        """Extract most relevant content for LLM classification"""
        if not body:
            return ""
        clean_body = self._clean_email_body(body)
        lines = clean_body.splitlines()
        key_lines = []
        for line in lines[:10]:
            line = line.strip()
            if len(line) > 15 and not line.lower().startswith(("best regards", "sincerely", "thanks", "sent from", "--")):
                key_lines.append(line)
                if len(" ".join(key_lines)) >= max_chars:
                    break
        return " ".join(key_lines)[:max_chars] or clean_body[:max_chars]

    # ----------------- Caching -----------------
    def _get_content_hash(self, email_data: Dict) -> str:
        content = f"{email_data.get('subject','')}{email_data.get('sender','')}{email_data.get('body','')[:500]}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cached_classification(self, email_data: Dict) -> Optional[Dict]:
        try:
            cache_file = self.cache_dir / f"{self._get_content_hash(email_data)}.json"
            if cache_file.exists():
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                cache_date = datetime.fromisoformat(cached["cached_at"])
                if datetime.now() - cache_date < timedelta(days=7):
                    return cached["classification"]
        except Exception:
            pass
        return None

    def _cache_classification(self, email_data: Dict, classification: Dict):
        try:
            cache_file = self.cache_dir / f"{self._get_content_hash(email_data)}.json"
            cache_file.write_text(json.dumps({
                "cached_at": datetime.now().isoformat(),
                "classification": classification,
                "email_id": email_data.get("id", "unknown")
            }, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"⚠️ Cache write failed: {e}")

    # ----------------- LLM classification -----------------
    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM asynchronously"""
        try:
            # instance-level LLM
            llm = getattr(self, "llm", None)
            if llm and hasattr(llm, "simple_chat"):
                return await asyncio.to_thread(llm.simple_chat, prompt)

            # server-level multi_llm_manager
            mgr = getattr(getattr(self, "server", None), "multi_llm_manager", None)
            if mgr and hasattr(mgr, "simple_chat"):
                return await asyncio.to_thread(mgr.simple_chat, prompt)

            # fallback OpenAI
            import openai
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                openai.api_key = api_key
                resp = await asyncio.to_thread(openai.ChatCompletion.create,
                                               model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
                                               messages=[{"role":"user","content":prompt}],
                                               max_tokens=1024,
                                               temperature=0.0)
                return resp.choices[0].message.content
        except Exception:
            return None

    def _extract_json_array(self, text: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        if not text:
            return None
        import re
        text = re.sub(r"```(?:json)?\n", "", text)
        text = re.sub(r"```$", "", text)
        m = re.search(r"(\[.*\])", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                try:
                    return json.loads(m.group(1).replace("'", '"'))
                except Exception:
                    return None
        return None

    async def classify_batch(self, email_batch: List[Dict], available_labels: List[str]) -> List[Dict]:
        """Classify a batch of emails asynchronously"""
        payload = []
        for e in email_batch:
            mid = e.get("id") or e.get("message_id") or e.get("threadId")
            snippet = self._extract_key_content(e.get("body","") or "")
            payload.append({"message_id": mid, "snippet": snippet[:512]})

        prompt = (
            "You are an assistant that maps emails to three labels: category, priority, action. "
            f"Available categories: {available_labels}. "
            "Return a JSON array where each element is "
            '{"message_id":"...","category":"...","priority":"low|medium|high","action":"delete|archive|keep_inbox","ai_generated":true|false}. '
            "Only return the JSON array. Emails:\n" + json.dumps(payload, ensure_ascii=False)
        )

        raw = await self._call_llm(prompt)
        parsed = self._extract_json_array(raw) or []

        # Normalize and fill defaults
        by_id = {str(item.get("message_id")): item for item in parsed if item.get("message_id")}
        normalized = []
        for item in payload:
            mid = str(item.get("message_id"))
            p = by_id.get(mid) or {}
            p.setdefault("message_id", mid)
            p.setdefault("category", "other")
            p.setdefault("priority", "low")
            p.setdefault("action", "keep_inbox")
            p.setdefault("ai_generated", False)
            normalized.append(p)
        return normalized

    async def classify_batches(self, email_batches: List[List[Dict]], available_labels: List[str]) -> List[List[Dict]]:
        """Classify all batches asynchronously"""
        tasks = [self.classify_batch(batch, available_labels) for batch in email_batches]
        return await asyncio.gather(*tasks)

    # ----------------- Apply labels -----------------
    async def apply_label(self, email: Dict, classification: Dict):
        async with self._gmail_lock:
            try:
                mid = email.get("id") or email.get("message_id")
                if mid is not None:
                    self._apply_category_label(str(mid), classification["category"])
                    classification["applied"] = True
                else:
                    classification["applied"] = False
            except Exception:
                classification["applied"] = False

    async def apply_label_batches(self, email_batches: List[List[Dict]], classified_batches: List[List[Dict]]):
        tasks = []
        for batch_emails, batch_cls in zip(email_batches, classified_batches):
            for email, cls in zip(batch_emails, batch_cls):
                tasks.append(self.apply_label(email, cls))
        await asyncio.gather(*tasks)

    # ----------------- Default classification -----------------
    def _default_classification(self) -> Dict:
        return {
            "category": "other",
            "priority": "low",
            "reasoning": "Default classification",
            "ai_generated": False
        }

    # ----------------- High-level reprocessing -----------------
    async def reprocess_existing_emails_async(self, email_ids: List[str], batch_size: int = 10, available_labels: Optional[List[str]] = None):
        """High-performance async reprocessing"""
        start_time = datetime.now()
        email_batches = [email_ids[i:i+batch_size] for i in range(0, len(email_ids), batch_size)]
        fetched_batches = await self.fetch_email_batches(email_ids, batch_size)
        available_labels = available_labels or list(self.categories.keys())

        classified_batches = await self.classify_batches(fetched_batches, available_labels)
        await self.apply_label_batches(fetched_batches, classified_batches)

        total_time = (datetime.now() - start_time).total_seconds()
        print(f"✅ Reprocessing complete: {len(email_ids)} emails in {total_time:.2f}s")
        return {
            "total_emails": len(email_ids),
            "processing_time": total_time,
            "emails_per_second": len(email_ids) / total_time if total_time > 0 else 0
        }


if __name__ == "__main__":
    print("🚀 Async High-Performance Gmail Organizer")
