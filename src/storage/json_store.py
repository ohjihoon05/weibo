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


# ---------------------------------------------------------------------------
# Metrics storage (003 - marketing automation)
# ---------------------------------------------------------------------------

def append_metrics(metric_dict: dict) -> None:
    """Append a performance metric entry to data/metrics/YYYY-MM.jsonl."""
    metrics_dir = get_data_dir() / "metrics"
    os.makedirs(metrics_dir, exist_ok=True)

    collected_at = datetime.fromisoformat(metric_dict["collected_at"])
    month_prefix = collected_at.strftime("%Y-%m")
    filepath = metrics_dir / f"{month_prefix}.jsonl"

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(metric_dict, ensure_ascii=False) + "\n")


def load_metrics(year_month: str | None = None) -> list[dict]:
    """Load performance metrics from data/metrics/.

    Args:
        year_month: Optional filter like '2026-02'. If None, loads current month.

    Returns:
        List of metric dictionaries.
    """
    metrics_dir = get_data_dir() / "metrics"
    if not metrics_dir.exists():
        return []

    if year_month is None:
        year_month = datetime.now().strftime("%Y-%m")

    filepath = metrics_dir / f"{year_month}.jsonl"
    if not filepath.exists():
        return []

    metrics = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                metrics.append(json.loads(line))
    return metrics


# ---------------------------------------------------------------------------
# Competitor storage (003 - marketing automation)
# ---------------------------------------------------------------------------

def save_competitors(competitors: list[dict]) -> None:
    """Save competitor account list to data/competitors.json."""
    filepath = get_data_dir() / "competitors.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(competitors, f, ensure_ascii=False, indent=2)


def load_competitors() -> list[dict]:
    """Load competitor account list from data/competitors.json."""
    filepath = get_data_dir() / "competitors.json"
    if not filepath.exists():
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def append_competitor_posts(posts: list[dict]) -> None:
    """Append scraped competitor posts to data/competitors/YYYY-MM.jsonl."""
    if not posts:
        return

    competitors_dir = get_data_dir() / "competitors"
    os.makedirs(competitors_dir, exist_ok=True)

    month_prefix = datetime.now().strftime("%Y-%m")
    filepath = competitors_dir / f"{month_prefix}.jsonl"

    with open(filepath, "a", encoding="utf-8") as f:
        for post in posts:
            f.write(json.dumps(post, ensure_ascii=False) + "\n")


def load_competitor_posts(year_month: str | None = None) -> list[dict]:
    """Load competitor posts from data/competitors/YYYY-MM.jsonl."""
    competitors_dir = get_data_dir() / "competitors"
    if not competitors_dir.exists():
        return []

    if year_month is None:
        year_month = datetime.now().strftime("%Y-%m")

    filepath = competitors_dir / f"{year_month}.jsonl"
    if not filepath.exists():
        return []

    posts = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                posts.append(json.loads(line))
    return posts


# ---------------------------------------------------------------------------
# Report storage (003 - marketing automation)
# ---------------------------------------------------------------------------

def save_report(report_dict: dict, year_week: str | None = None) -> str:
    """Save a benchmark or weekly report to data/reports/YYYY-WW.json.

    Args:
        report_dict: Report data dictionary.
        year_week: Optional key like '2026-08'. If None, uses current week.

    Returns:
        The file path of the saved report.
    """
    reports_dir = get_data_dir() / "reports"
    os.makedirs(reports_dir, exist_ok=True)

    if year_week is None:
        now = datetime.now()
        year_week = f"{now.year}-{now.isocalendar()[1]:02d}"

    filepath = reports_dir / f"{year_week}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)

    return str(filepath)


def load_report(year_week: str) -> dict | None:
    """Load a report from data/reports/YYYY-WW.json."""
    filepath = get_data_dir() / "reports" / f"{year_week}.json"
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Expert content storage (003 - marketing automation)
# ---------------------------------------------------------------------------

def append_expert_content(content_dict: dict) -> None:
    """Append expert content entry to data/expert_content/YYYY-MM.jsonl."""
    expert_dir = get_data_dir() / "expert_content"
    os.makedirs(expert_dir, exist_ok=True)

    month_prefix = datetime.now().strftime("%Y-%m")
    filepath = expert_dir / f"{month_prefix}.jsonl"

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(content_dict, ensure_ascii=False) + "\n")


def load_expert_content(year_month: str | None = None) -> list[dict]:
    """Load expert content from data/expert_content/YYYY-MM.jsonl."""
    expert_dir = get_data_dir() / "expert_content"
    if not expert_dir.exists():
        return []

    if year_month is None:
        year_month = datetime.now().strftime("%Y-%m")

    filepath = expert_dir / f"{year_month}.jsonl"
    if not filepath.exists():
        return []

    entries = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def list_recent_posts(limit: int = 20) -> list[dict]:
    """Load the most recent posts from data/posts/, sorted by creation date.

    Args:
        limit: Maximum number of posts to return.

    Returns:
        List of post dicts, most recent first.
    """
    posts_dir = get_data_dir() / "posts"
    if not posts_dir.exists():
        return []

    post_files = sorted(posts_dir.glob("*.json"), reverse=True)
    posts = []
    for fp in post_files[:limit]:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                posts.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return posts
