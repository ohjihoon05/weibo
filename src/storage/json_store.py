"""JSON file-based storage module.

Provides functions to save/load posts, append history entries,
and manage exchange rate cache using local JSON files under data/.
"""

import json
import os
from datetime import datetime
from pathlib import Path


def _find_project_root() -> Path:
    """Detect the project root by walking up from this file's directory
    until finding a directory that contains 'src/'."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "src").is_dir():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root (directory containing src/)")


def get_data_dir() -> Path:
    """Return the data/ directory path (project_root/data).

    Creates the directory if it does not already exist.
    """
    data_dir = _find_project_root() / "data"
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def save_post(post_dict: dict) -> str:
    """Save a post to data/posts/YYYY-MM-DD_{id}.json.

    Args:
        post_dict: A dictionary from Post.to_dict(), expected to contain
                   'created_at' (ISO-format timestamp) and 'id' fields.

    Returns:
        The file path of the saved JSON file as a string.
    """
    posts_dir = get_data_dir() / "posts"
    os.makedirs(posts_dir, exist_ok=True)

    created_at = datetime.fromisoformat(post_dict["created_at"])
    date_prefix = created_at.strftime("%Y-%m-%d")
    post_id = post_dict["id"]

    filename = f"{date_prefix}_{post_id}.json"
    filepath = posts_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(post_dict, f, ensure_ascii=False, indent=2)

    return str(filepath)


def load_post(post_id: str) -> dict | None:
    """Load a post by ID from data/posts/.

    Scans the posts directory for a file ending with '_{post_id}.json'.

    Args:
        post_id: The post ID to search for.

    Returns:
        The post dictionary if found, or None if not found.
    """
    posts_dir = get_data_dir() / "posts"
    if not posts_dir.exists():
        return None

    suffix = f"_{post_id}.json"
    for entry in posts_dir.iterdir():
        if entry.is_file() and entry.name.endswith(suffix):
            with open(entry, "r", encoding="utf-8") as f:
                return json.load(f)

    return None


def append_history(history_dict: dict) -> None:
    """Append a PostHistory entry as a JSON line to data/history/YYYY-MM.jsonl.

    Uses the history's 'timestamp' field to determine which monthly file
    to append to.

    Args:
        history_dict: A dictionary from PostHistory, expected to contain
                      a 'timestamp' field (ISO-format timestamp).
    """
    history_dir = get_data_dir() / "history"
    os.makedirs(history_dir, exist_ok=True)

    timestamp = datetime.fromisoformat(history_dict["timestamp"])
    month_prefix = timestamp.strftime("%Y-%m")

    filepath = history_dir / f"{month_prefix}.jsonl"

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(history_dict, ensure_ascii=False) + "\n")


def save_exchange_rate(rate_data: dict) -> None:
    """Save exchange rate cache to data/exchange_rate.json.

    Args:
        rate_data: A dictionary with keys 'rate', 'source', 'fetched_at'.
    """
    filepath = get_data_dir() / "exchange_rate.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(rate_data, f, ensure_ascii=False, indent=2)


def load_exchange_rate() -> dict | None:
    """Load exchange rate cache from data/exchange_rate.json.

    Returns:
        The exchange rate dictionary if the file exists, or None otherwise.
    """
    filepath = get_data_dir() / "exchange_rate.json"

    if not filepath.exists():
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cookie_data(data: dict, path: str) -> None:
    """Save cookie data to a JSON file with restricted permissions (600).

    Args:
        data: Cookie data dictionary to persist.
        path: Absolute or relative file path.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.chmod(path, 0o600)


def load_cookie_data(path: str) -> dict | None:
    """Load cookie data from a JSON file.

    Args:
        path: Absolute or relative file path.

    Returns:
        The cookie data dictionary if the file exists, or None otherwise.
    """
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
