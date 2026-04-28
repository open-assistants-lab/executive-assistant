"""Gmail email cache using HybridDB.

Fetches from Gmail API (via gws CLI), stores in HybridDB for
keyed-by-message-id access + keyword/semantic/hybrid search.

Store path: data/users/{user_id}/gmail_cache/
  app.db     — SQLite + FTS5 + journal
  vectors/   — ChromaDB for semantic search
"""

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from src.app_logging import get_logger
from src.sdk.hybrid_db import HybridDB, SearchMode
from src.storage.paths import get_paths

logger = get_logger()

TABLE = "emails"
_JSON_FIELDS = {"labels", "headers", "to_addr"}
_LIST_FIELDS = {"to_addr", "labels"}


@dataclass
class EmailResult:
    """A cached email row."""

    id: int
    message_id: str
    thread_id: str
    from_addr: str
    to_addr: list[str]
    subject: str
    snippet: str
    body: str
    ts: int
    labels: list[str]
    headers: dict[str, str]
    _score: float = 0.0


def _serialize(value: Any, field_name: str) -> str | None:
    """Serialize a field value for HybridDB storage."""
    if value is None:
        return None
    if field_name in _JSON_FIELDS:
        return json.dumps(value) if not isinstance(value, str) else value
    if field_name in _LIST_FIELDS:
        if isinstance(value, list):
            return ", ".join(value)
        return str(value)
    return str(value)


def _deserialize(value: Any, field_name: str) -> Any:
    """Deserialize a field value from HybridDB."""
    if value is None:
        return [] if field_name in _LIST_FIELDS else ({} if field_name == "headers" else None)
    if field_name in _JSON_FIELDS:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {} if field_name == "headers" else []
        return value
    if field_name in _LIST_FIELDS:
        if isinstance(value, str) and value.strip():
            return [v.strip() for v in value.split(",")]
        return []
    if field_name == "ts":
        return int(value) if value else 0
    return value


class GmailCache:
    """HybridDB-backed Gmail email cache."""

    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        base_path = get_paths(user_id).gmail_cache()
        base_path.mkdir(parents=True, exist_ok=True)

        self.db = HybridDB(str(base_path))
        self.db.create_table(
            TABLE,
            {
                "message_id": "TEXT",
                "thread_id": "TEXT",
                "from_addr": "TEXT",
                "to_addr": "TEXT",
                "subject": "TEXT",
                "snippet": "LONGTEXT",
                "body": "LONGTEXT",
                "ts": "INTEGER",
                "labels": "JSON",
                "headers": "JSON",
            },
        )

    # -- CRUD --

    def upsert(self, email: dict) -> int | None:
        """Insert or update an email by Gmail message_id. Returns row id."""
        msg_id = email.get("message_id")
        if not msg_id:
            logger.warning("gmail_upsert_no_id", {"reason": "missing message_id"})
            return None

        existing = self.db.query(TABLE, where="message_id = ?", params=(msg_id,), limit=1)

        row = {
            "message_id": msg_id,
            "thread_id": _serialize(email.get("thread_id"), "thread_id"),
            "from_addr": _serialize(email.get("from_addr"), "from_addr"),
            "to_addr": _serialize(email.get("to_addr"), "to_addr"),
            "subject": _serialize(email.get("subject"), "subject"),
            "snippet": _serialize(email.get("snippet"), "snippet"),
            "body": _serialize(email.get("body"), "body"),
            "ts": _serialize(email.get("ts"), "ts"),
            "labels": _serialize(email.get("labels"), "labels"),
            "headers": _serialize(email.get("headers"), "headers"),
        }

        if existing:
            row_id = existing[0]["id"]
            self.db.update(TABLE, row_id, row)
            return row_id
        else:
            return self.db.insert(TABLE, row)

    def upsert_batch(self, emails: list[dict]) -> int:
        """Insert or update multiple emails. Returns count upserted."""
        count = 0
        for email in emails:
            if self.upsert(email) is not None:
                count += 1
        return count

    def get_by_message_id(self, message_id: str) -> EmailResult | None:
        """Get a single email by Gmail message_id."""
        rows = self.db.query(TABLE, where="message_id = ?", params=(message_id,), limit=1)
        if not rows:
            return None
        return self._row_to_result(rows[0])

    def get_recent(self, limit: int = 20) -> list[EmailResult]:
        """Get most recent emails by timestamp."""
        rows = self.db.query(TABLE, order_by="ts DESC", limit=limit)
        return [self._row_to_result(r) for r in rows]

    def count(self) -> int:
        return self.db.count(TABLE)

    # -- Search --

    def search_keyword(self, query: str, limit: int = 10) -> list[EmailResult]:
        """Keyword search across subject, snippet, body (FTS5)."""
        if not query:
            return self.get_recent(limit)
        rows = self.db.search(TABLE, "body", query, mode=SearchMode.KEYWORD, limit=limit)
        return [self._row_to_result(r) for r in rows]

    def search_semantic(self, query: str, limit: int = 10) -> list[EmailResult]:
        """Semantic search across snippet and body (ChromaDB)."""
        if not query:
            return self.get_recent(limit)
        rows = self.db.search(TABLE, "body", query, mode=SearchMode.SEMANTIC, limit=limit)
        return [self._row_to_result(r) for r in rows]

    def search_hybrid(
        self,
        query: str,
        limit: int = 10,
        fts_weight: float = 0.5,
        recency_weight: float = 0.3,
        from_addr: str | None = None,
        labels: list[str] | None = None,
    ) -> list[EmailResult]:
        """Hybrid search with optional filters."""
        if not query:
            return self.get_recent(limit)

        where: dict[str, Any] | None = None
        if from_addr or labels:
            where = {}
            if from_addr:
                where["from_addr"] = from_addr
            if labels:
                where["labels"] = {"$contains": labels} if len(labels) > 1 else labels[0]

        rows = self.db.search(
            TABLE,
            "body",
            query,
            mode=SearchMode.HYBRID,
            limit=limit,
            fts_weight=fts_weight,
            recency_weight=recency_weight,
            recency_column="ts",
            where=where,
        )
        return [self._row_to_result(r) for r in rows]

    def query_by_label(self, label: str, limit: int = 50) -> list[EmailResult]:
        """Get emails with a specific label (e.g. INBOX, SENT, UNREAD)."""
        rows = self.db.query(
            TABLE,
            where="labels LIKE ?",
            params=(f"%{label}%",),
            order_by="ts DESC",
            limit=limit,
        )
        return [self._row_to_result(r) for r in rows]

    # -- Helpers --

    def clear(self) -> None:
        all_rows = self.db.query(TABLE, limit=100000)
        for r in all_rows:
            self.db.delete(TABLE, r["id"])

    def stats(self) -> dict:
        return {
            "total": self.db.count(TABLE),
            "health": self.db.health(TABLE),
            "journal": self.db.journal_status(TABLE),
        }

    def _row_to_result(self, row: dict) -> EmailResult:
        score = row.get("_score", 0.0)
        return EmailResult(
            id=row["id"],
            message_id=_deserialize(row.get("message_id"), "message_id"),
            thread_id=_deserialize(row.get("thread_id"), "thread_id"),
            from_addr=_deserialize(row.get("from_addr"), "from_addr"),
            to_addr=_deserialize(row.get("to_addr"), "to_addr"),
            subject=_deserialize(row.get("subject"), "subject"),
            snippet=_deserialize(row.get("snippet"), "snippet"),
            body=_deserialize(row.get("body"), "body"),
            ts=_deserialize(row.get("ts"), "ts"),
            labels=_deserialize(row.get("labels"), "labels"),
            headers=_deserialize(row.get("headers"), "headers"),
            _score=score,
        )


# -- Singleton cache --

_stores: dict[str, GmailCache] = {}


def get_gmail_cache(user_id: str = "default_user") -> GmailCache:
    if user_id not in _stores:
        _stores[user_id] = GmailCache(user_id)
    return _stores[user_id]


# -- Sync from Gmail API via gws CLI --

_GSW_FETCH_TIMEOUT = 30
_LIST_PAGE_SIZE = 500
_UPSERT_FLUSH = 25


def sync_emails(
    user_id: str = "default_user",
    max_results: int = 50,
    query: str | None = None,
    fetch_body: bool = True,
    progress: bool = True,
) -> dict:
    """Sync emails from Gmail API into the cache.

    Uses the gws CLI (must be installed and authenticated).
    Auto-paginates through all matching results.

    Returns dict with counts: {listed, fetched, upserted, errors}
    """
    cache = get_gmail_cache(user_id)

    # -- Step 1: Paginate through all matching message IDs --
    all_messages: list[dict] = []
    page_token: str | None = None
    pages = 0

    while True:
        params: dict[str, Any] = {"userId": "me", "maxResults": _LIST_PAGE_SIZE}
        if query:
            params["q"] = query
        if page_token:
            params["pageToken"] = page_token

        list_json = _run_gws("gmail", "users", "messages", "list", params)
        pages += 1

        if list_json is None:
            # Retry once if not the first page
            if pages == 1:
                return {"listed": 0, "fetched": 0, "upserted": 0, "errors": 1}
            break

        messages = list_json.get("messages", [])
        all_messages.extend(messages)

        page_token = list_json.get("nextPageToken")
        if not page_token or len(all_messages) >= max_results:
            break

    if not all_messages:
        return {"listed": 0, "fetched": 0, "upserted": 0, "errors": 0}

    total = len(all_messages)
    logger.info("gmail_sync_listed", {"total": total, "pages": pages})

    # -- Step 2: Fetch details and upsert in batches --
    fetched = 0
    upserted = 0
    errors = 0
    batch: list[dict] = []

    for i, msg in enumerate(all_messages):
        msg_id = msg["id"]
        thread_id = msg.get("threadId", msg_id)
        email_data = _fetch_one_email(msg_id, thread_id, fetch_body)

        if email_data:
            batch.append(email_data)
            fetched += 1
        else:
            errors += 1

        # Flush batch periodically
        if len(batch) >= _UPSERT_FLUSH:
            upserted += cache.upsert_batch(batch)
            batch.clear()

        if progress and (i + 1) % 10 == 0:
            print(f"  {i + 1}/{total} ...", end="\r", flush=True)

    # Flush remaining
    if batch:
        upserted += cache.upsert_batch(batch)

    if progress:
        print(f"  {total}/{total} done.             ")

    cache.db.process_journal(limit=10000)

    return {"listed": total, "fetched": fetched, "upserted": upserted, "errors": errors}


def _fetch_one_email(
    message_id: str,
    thread_id: str,
    fetch_body: bool = True,
) -> dict | None:
    """Fetch a single email's metadata (and optionally body) via gws."""
    meta_headers = ["From", "To", "Date", "Subject", "List-Unsubscribe", "List-Unsubscribe-Post"]

    params: dict[str, Any] = {
        "userId": "me",
        "id": message_id,
        "format": "full" if fetch_body else "metadata",
    }
    if not fetch_body:
        params["metadataHeaders"] = meta_headers

    data = _run_gws("gmail", "users", "messages", "get", params)
    if data is None:
        return None

    payload = data.get("payload", {})
    headers_dict = {}
    for h in payload.get("headers", []):
        headers_dict[h["name"]] = h["value"]

    # Parse timestamp
    date_str = headers_dict.get("Date", "")
    ts = _parse_date_to_ts(date_str)

    # Extract body
    body = ""
    if fetch_body:
        body = _extract_body(payload)

    # Parse recipients
    to_raw = headers_dict.get("To", "")
    to_list = _parse_address_list(to_raw) if to_raw else []

    # Labels
    labels = data.get("labelIds", [])

    # Headers we care about
    important_headers = {}
    for key in ["List-Unsubscribe", "List-Unsubscribe-Post", "Message-ID", "In-Reply-To", "References"]:
        val = headers_dict.get(key, "")
        if val:
            important_headers[key] = val

    return {
        "message_id": message_id,
        "thread_id": thread_id,
        "from_addr": headers_dict.get("From", ""),
        "to_addr": to_list,
        "subject": headers_dict.get("Subject", "(no subject)"),
        "snippet": data.get("snippet", ""),
        "body": body,
        "ts": ts,
        "labels": labels,
        "headers": important_headers,
    }


def _extract_body(payload: dict) -> str:
    """Extract plain text body from a Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            import base64

            try:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            except Exception:
                return ""
        return ""

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    # Fallback: try HTML if no plain text
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                import base64

                try:
                    html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    return _strip_html(html)
                except Exception:
                    pass

    return ""


def _strip_html(html: str) -> str:
    """Basic HTML tag stripping to get readable text."""
    import re

    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


def _parse_date_to_ts(date_str: str) -> int:
    """Parse an email Date header to Unix timestamp."""
    if not date_str:
        return 0
    from email.utils import parsedate_to_datetime

    try:
        return int(parsedate_to_datetime(date_str).timestamp())
    except Exception:
        return 0


def _parse_address_list(raw: str) -> list[str]:
    """Parse a comma-separated address list like '\"Name\" <a@b.com>, <c@d.com>'."""
    if not raw:
        return []
    from email.utils import getaddresses

    try:
        return [addr for name, addr in getaddresses([raw]) if addr]
    except Exception:
        return [a.strip() for a in raw.split(",") if a.strip()]


def _run_gws(
    service: str,
    resource: str,
    sub_resource: str,
    method: str,
    params: dict,
) -> dict | None:
    """Run a gws CLI command and return JSON output."""
    cmd = [
        "gws",
        service,
        resource,
        sub_resource,
        method,
        "--params",
        json.dumps(params),
        "--format",
        "json",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error("gws_failed", {"exit": result.returncode, "stderr": result.stderr[:200]})
            return None

        # stderr contains "Using keyring backend: ...", stdout is JSON
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.error("gws_timeout", {"reason": "subprocess timeout"})
        return None
    except json.JSONDecodeError as e:
        logger.error("gws_json_error", {"error": str(e)})
        return None
    except Exception as e:
        logger.error("gws_error", {"error": str(e)})
        return None
