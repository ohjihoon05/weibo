"""JSON file-based publish queue with atomic writes and file locking.

Provides crash-safe queue operations for scheduling Weibo posts.
Uses fcntl advisory locks and atomic rename for data integrity.
"""

import fcntl
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from src.models.queue_item import QueueItem, QueueItemStatus

logger = logging.getLogger(__name__)


def _find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "src").is_dir():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root")


QUEUE_FILE = _find_project_root() / "data" / "publish_queue.json"

# Max time an item can stay in 'processing' before considered stale (seconds)
STALE_PROCESSING_TIMEOUT = 600  # 10 minutes


class JsonPublishQueue:
    """Thread-safe JSON file-based publish queue."""

    def __init__(self, queue_file: str | Path | None = None):
        self._queue_file = Path(queue_file) if queue_file else QUEUE_FILE
        os.makedirs(self._queue_file.parent, exist_ok=True)
        if not self._queue_file.exists():
            self._atomic_write([])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, item: QueueItem) -> None:
        """Add an item to the queue."""
        with self._lock():
            items = self._read()
            items.append(item.to_dict())
            self._atomic_write(items)
        logger.info("Enqueued item %s (type=%s, scheduled=%s)",
                     item.id, item.type, item.scheduled_at)

    def dequeue(self) -> QueueItem | None:
        """Get the next pending item whose scheduled time has passed.

        Marks the item as 'processing' atomically.

        Returns:
            The next QueueItem ready for processing, or None.
        """
        now = datetime.utcnow().isoformat()
        with self._lock():
            items = self._read()
            for i, data in enumerate(items):
                if (data["status"] == QueueItemStatus.pending.value
                        and data["scheduled_at"] <= now):
                    item = QueueItem.from_dict(data)
                    item.mark_processing()
                    items[i] = item.to_dict()
                    self._atomic_write(items)
                    logger.info("Dequeued item %s", item.id)
                    return item
        return None

    def complete(self, item_id: str, post_id: str) -> None:
        """Mark an item as completed."""
        with self._lock():
            items = self._read()
            for i, data in enumerate(items):
                if data["id"] == item_id:
                    item = QueueItem.from_dict(data)
                    item.mark_completed(post_id)
                    items[i] = item.to_dict()
                    self._atomic_write(items)
                    logger.info("Completed item %s (post_id=%s)", item_id, post_id)
                    return
        logger.warning("Item %s not found for completion", item_id)

    def fail(self, item_id: str, error: str) -> None:
        """Mark an item as failed."""
        with self._lock():
            items = self._read()
            for i, data in enumerate(items):
                if data["id"] == item_id:
                    item = QueueItem.from_dict(data)
                    item.mark_failed(error)
                    items[i] = item.to_dict()
                    self._atomic_write(items)
                    logger.info("Failed item %s: %s", item_id, error)
                    return
        logger.warning("Item %s not found for failure", item_id)

    def get_pending(self) -> list[QueueItem]:
        """Return all pending items sorted by scheduled_at."""
        items = self._read()
        pending = [
            QueueItem.from_dict(d) for d in items
            if d["status"] == QueueItemStatus.pending.value
        ]
        pending.sort(key=lambda x: x.scheduled_at)
        return pending

    def get_pending_count(self) -> int:
        """Return the count of pending items."""
        return len(self.get_pending())

    def get_all(self) -> list[QueueItem]:
        """Return all items in the queue."""
        items = self._read()
        return [QueueItem.from_dict(d) for d in items]

    def get_item(self, item_id: str) -> QueueItem | None:
        """Get a specific item by ID."""
        items = self._read()
        for data in items:
            if data["id"] == item_id:
                return QueueItem.from_dict(data)
        return None

    def remove(self, item_id: str) -> bool:
        """Remove an item from the queue."""
        with self._lock():
            items = self._read()
            new_items = [d for d in items if d["id"] != item_id]
            if len(new_items) < len(items):
                self._atomic_write(new_items)
                logger.info("Removed item %s", item_id)
                return True
        return False

    def update_schedule(self, item_id: str, new_scheduled_at: str) -> bool:
        """Change the scheduled time for a pending item."""
        with self._lock():
            items = self._read()
            for i, data in enumerate(items):
                if data["id"] == item_id and data["status"] == QueueItemStatus.pending.value:
                    data["scheduled_at"] = new_scheduled_at
                    items[i] = data
                    self._atomic_write(items)
                    logger.info("Rescheduled item %s to %s", item_id, new_scheduled_at)
                    return True
        return False

    def cleanup(self, max_age_days: int = 30) -> int:
        """Remove completed/failed items older than max_age_days.

        Returns:
            Number of items removed.
        """
        cutoff = datetime.utcnow()
        removed = 0
        with self._lock():
            items = self._read()
            new_items = []
            for data in items:
                if data["status"] in (QueueItemStatus.completed.value, QueueItemStatus.failed.value):
                    completed_at = data.get("completed_at")
                    if completed_at:
                        age = (cutoff - datetime.fromisoformat(completed_at)).days
                        if age > max_age_days:
                            removed += 1
                            continue
                new_items.append(data)
            self._atomic_write(new_items)
        if removed:
            logger.info("Cleaned up %d old items", removed)
        return removed

    def recover_stale_processing(self) -> int:
        """Reset items stuck in 'processing' back to 'pending'.

        Called on bot startup to recover from crashes during processing.

        Returns:
            Number of items recovered.
        """
        now = datetime.utcnow()
        recovered = 0
        with self._lock():
            items = self._read()
            for i, data in enumerate(items):
                if data["status"] == QueueItemStatus.processing.value:
                    started = data.get("started_at")
                    if started:
                        elapsed = (now - datetime.fromisoformat(started)).total_seconds()
                        if elapsed > STALE_PROCESSING_TIMEOUT:
                            item = QueueItem.from_dict(data)
                            item.reset_to_pending()
                            items[i] = item.to_dict()
                            recovered += 1
                    else:
                        # No started_at but processing — reset
                        item = QueueItem.from_dict(data)
                        item.reset_to_pending()
                        items[i] = item.to_dict()
                        recovered += 1
            if recovered:
                self._atomic_write(items)
                logger.info("Recovered %d stale processing items", recovered)
        return recovered

    def get_today_completed_count(self) -> int:
        """Count how many items were completed today (UTC)."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        items = self._read()
        return sum(
            1 for d in items
            if d["status"] == QueueItemStatus.completed.value
            and d.get("completed_at", "").startswith(today)
        )

    # ------------------------------------------------------------------
    # File operations with locking and atomic writes
    # ------------------------------------------------------------------

    def _lock(self):
        """Return a context manager that holds an exclusive lock on the queue file."""
        return _FileLock(self._queue_file)

    def _read(self) -> list[dict]:
        """Read the queue file. Returns empty list if file doesn't exist or is empty."""
        if not self._queue_file.exists():
            return []
        try:
            with open(self._queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read queue file, returning empty list")
            return []

    def _atomic_write(self, items: list[dict]) -> None:
        """Write items to queue file atomically using tempfile + rename."""
        dir_path = self._queue_file.parent
        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            os.rename(tmp_path, str(self._queue_file))
        except OSError:
            logger.exception("Atomic write failed")
            # Clean up temp file if rename failed
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise


class _FileLock:
    """Context manager for fcntl-based exclusive file locking."""

    def __init__(self, queue_file: Path):
        self._lock_file = queue_file.with_suffix(".lock")

    def __enter__(self):
        self._fd = open(self._lock_file, "w")
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        self._fd.close()
        return False
