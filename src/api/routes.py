"""Flask internal API server for OpenClaw skill integration.

Exposes queue, competitor, analytics, and expert endpoints as JSON APIs.
Bound to localhost:5000 only -- no authentication required.
"""

import logging
from datetime import datetime

from flask import Flask, Blueprint, jsonify, request

from src.storage.publish_queue import JsonPublishQueue
from src.storage.json_store import (
    load_competitors,
    save_competitors,
    load_metrics,
    load_competitor_posts,
    list_recent_posts,
    load_expert_content,
    load_report,
)
from src.models.queue_item import QueueItem, QueueItemType
from src.models.competitor import CompetitorAccount
from src.services.scheduler import get_next_publish_time, calculate_optimal_times

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------

queue_bp = Blueprint("queue", __name__, url_prefix="/api/queue")
competitors_bp = Blueprint("competitors", __name__, url_prefix="/api/competitors")
analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")
expert_bp = Blueprint("expert", __name__, url_prefix="/api/expert")


def _get_queue() -> JsonPublishQueue:
    """Retrieve the publish queue instance from Flask app config."""
    from flask import current_app
    return current_app.config["PUBLISH_QUEUE"]


# ===================================================================
# Queue endpoints
# ===================================================================

@queue_bp.route("/status", methods=["GET"])
def queue_status():
    """Return pending count, today's completed count, and queue items summary."""
    try:
        pq = _get_queue()
        pending = pq.get_pending()
        today_completed = pq.get_today_completed_count()
        items_summary = [
            {
                "id": item.id,
                "type": item.type,
                "status": item.status,
                "scheduled_at": item.scheduled_at,
                "text_preview": item.text[:80] if item.text else "",
            }
            for item in pending
        ]
        return jsonify({
            "pending_count": len(pending),
            "today_completed_count": today_completed,
            "items": items_summary,
        })
    except Exception as exc:
        logger.exception("Error fetching queue status: %s", exc)
        return jsonify({"error": str(exc)}), 500


@queue_bp.route("/items", methods=["GET"])
def queue_items():
    """Return all pending items."""
    try:
        pq = _get_queue()
        pending = pq.get_pending()
        return jsonify({
            "count": len(pending),
            "items": [item.to_dict() for item in pending],
        })
    except Exception as exc:
        logger.exception("Error fetching queue items: %s", exc)
        return jsonify({"error": str(exc)}), 500


@queue_bp.route("/enqueue", methods=["POST"])
def queue_enqueue():
    """Enqueue a new item.

    JSON body:
        text (str, required): Post text content.
        type (str, optional): "listing" or "expert". Defaults to "listing".
        image_paths (list[str], optional): List of local image file paths.
    """
    try:
        data = request.get_json(force=True)
        if not data or not data.get("text"):
            return jsonify({"error": "Missing required field: text"}), 400

        item_type = data.get("type", QueueItemType.listing.value)
        if item_type not in [t.value for t in QueueItemType]:
            return jsonify({"error": f"Invalid type: {item_type}"}), 400

        pq = _get_queue()
        scheduled_at = get_next_publish_time(pq)

        item = QueueItem(
            type=item_type,
            text=data["text"],
            image_paths=data.get("image_paths", []),
            scheduled_at=scheduled_at,
        )
        pq.enqueue(item)

        return jsonify({
            "message": "Item enqueued successfully",
            "item": item.to_dict(),
        }), 201
    except Exception as exc:
        logger.exception("Error enqueuing item: %s", exc)
        return jsonify({"error": str(exc)}), 500


@queue_bp.route("/publish/<item_id>", methods=["POST"])
def queue_publish(item_id: str):
    """Immediately publish an item by setting its scheduled_at to now.

    This reschedules the item so the next scheduler tick picks it up
    immediately.
    """
    try:
        pq = _get_queue()
        item = pq.get_item(item_id)
        if not item:
            return jsonify({"error": f"Item not found: {item_id}"}), 404

        if item.status != "pending":
            return jsonify({
                "error": f"Item is not pending (status={item.status})",
            }), 409

        # Set scheduled_at to now so the scheduler dequeues it immediately
        now_iso = datetime.utcnow().isoformat()
        updated = pq.update_schedule(item_id, now_iso)
        if not updated:
            return jsonify({"error": "Failed to update schedule"}), 500

        return jsonify({
            "message": "Item scheduled for immediate publish",
            "item_id": item_id,
            "scheduled_at": now_iso,
        })
    except Exception as exc:
        logger.exception("Error publishing item %s: %s", item_id, exc)
        return jsonify({"error": str(exc)}), 500


@queue_bp.route("/<item_id>", methods=["DELETE"])
def queue_delete(item_id: str):
    """Remove an item from the queue."""
    try:
        pq = _get_queue()
        removed = pq.remove(item_id)
        if not removed:
            return jsonify({"error": f"Item not found: {item_id}"}), 404

        return jsonify({"message": "Item removed", "item_id": item_id})
    except Exception as exc:
        logger.exception("Error deleting item %s: %s", item_id, exc)
        return jsonify({"error": str(exc)}), 500


# ===================================================================
# Competitor endpoints
# ===================================================================

@competitors_bp.route("", methods=["GET"])
def list_competitors():
    """List all competitors."""
    try:
        competitors = load_competitors()
        return jsonify({
            "count": len(competitors),
            "competitors": competitors,
        })
    except Exception as exc:
        logger.exception("Error listing competitors: %s", exc)
        return jsonify({"error": str(exc)}), 500


@competitors_bp.route("", methods=["POST"])
def add_competitor():
    """Add a new competitor.

    JSON body:
        uid (str, required): Weibo user ID.
        note (str, optional): Description or note about the competitor.
    """
    try:
        data = request.get_json(force=True)
        if not data or not data.get("uid"):
            return jsonify({"error": "Missing required field: uid"}), 400

        competitors = load_competitors()

        # Check for duplicates
        existing_uids = {c.get("uid") for c in competitors}
        if data["uid"] in existing_uids:
            return jsonify({"error": f"Competitor already exists: {data['uid']}"}), 409

        account = CompetitorAccount(
            uid=data["uid"],
            note=data.get("note", ""),
            source="manual",
        )
        competitors.append(account.to_dict())
        save_competitors(competitors)

        return jsonify({
            "message": "Competitor added",
            "competitor": account.to_dict(),
        }), 201
    except Exception as exc:
        logger.exception("Error adding competitor: %s", exc)
        return jsonify({"error": str(exc)}), 500


@competitors_bp.route("/<uid>", methods=["DELETE"])
def remove_competitor(uid: str):
    """Remove a competitor by UID."""
    try:
        competitors = load_competitors()
        original_count = len(competitors)
        competitors = [c for c in competitors if c.get("uid") != uid]

        if len(competitors) == original_count:
            return jsonify({"error": f"Competitor not found: {uid}"}), 404

        save_competitors(competitors)
        return jsonify({"message": "Competitor removed", "uid": uid})
    except Exception as exc:
        logger.exception("Error removing competitor %s: %s", uid, exc)
        return jsonify({"error": str(exc)}), 500


@competitors_bp.route("/benchmark", methods=["GET"])
def benchmark_report():
    """Get the latest benchmark report.

    Checks the current and previous week for a saved report.
    """
    try:
        now = datetime.now()
        current_week = f"{now.year}-{now.isocalendar()[1]:02d}"
        report = load_report(current_week)

        if not report:
            # Try previous week
            from datetime import timedelta
            prev = now - timedelta(weeks=1)
            prev_week = f"{prev.year}-{prev.isocalendar()[1]:02d}"
            report = load_report(prev_week)

        if not report:
            return jsonify({"error": "No benchmark report available"}), 404

        return jsonify(report)
    except Exception as exc:
        logger.exception("Error fetching benchmark report: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ===================================================================
# Analytics endpoints
# ===================================================================

@analytics_bp.route("/metrics", methods=["GET"])
def analytics_metrics():
    """Get recent metrics.

    Query params:
        month (str, optional): Year-month filter like "2026-02".
                                Defaults to current month.
    """
    try:
        month = request.args.get("month")
        metrics = load_metrics(year_month=month)
        return jsonify({
            "count": len(metrics),
            "month": month or datetime.now().strftime("%Y-%m"),
            "metrics": metrics,
        })
    except Exception as exc:
        logger.exception("Error fetching metrics: %s", exc)
        return jsonify({"error": str(exc)}), 500


@analytics_bp.route("/report", methods=["GET"])
def analytics_report():
    """Get the latest weekly performance report.

    Generates a fresh report from stored metrics and posts.
    """
    try:
        from src.services.benchmark_analyzer import BenchmarkAnalyzer
        analyzer = BenchmarkAnalyzer()
        report = analyzer.generate_weekly_report()

        if report.get("error"):
            return jsonify(report), 404

        return jsonify(report)
    except Exception as exc:
        logger.exception("Error generating weekly report: %s", exc)
        return jsonify({"error": str(exc)}), 500


@analytics_bp.route("/besttime", methods=["GET"])
def analytics_besttime():
    """Get optimal posting time analysis.

    Returns the calculated best times based on competitor and own
    performance data, plus the current configured publish times.
    """
    try:
        from src.config import PUBLISH_TIMES
        optimal = calculate_optimal_times()
        return jsonify({
            "optimal_times_cst": [
                {"hour": h, "minute": m} for h, m in optimal
            ],
            "configured_times_cst": [
                {"hour": h, "minute": m} for h, m in PUBLISH_TIMES
            ],
            "note": "Times are in China Standard Time (UTC+8)",
        })
    except Exception as exc:
        logger.exception("Error calculating optimal times: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ===================================================================
# Expert endpoints
# ===================================================================

@expert_bp.route("/recent", methods=["GET"])
def expert_recent():
    """List recent expert content.

    Query params:
        month (str, optional): Year-month filter like "2026-02".
                                Defaults to current month.
        limit (int, optional): Max items to return. Defaults to 20.
    """
    try:
        month = request.args.get("month")
        limit = request.args.get("limit", 20, type=int)
        entries = load_expert_content(year_month=month)

        # Return most recent first, limited
        entries = list(reversed(entries))[:limit]

        return jsonify({
            "count": len(entries),
            "month": month or datetime.now().strftime("%Y-%m"),
            "entries": entries,
        })
    except Exception as exc:
        logger.exception("Error fetching expert content: %s", exc)
        return jsonify({"error": str(exc)}), 500


@expert_bp.route("/generate", methods=["POST"])
def expert_generate():
    """Trigger expert content generation.

    JSON body (all optional):
        topic (str): ExpertTopic value to generate for.
                     If omitted, auto-selects least recently used topic.

    Returns the generated content or an error.
    """
    try:
        from src.services.expert_generator import ExpertGenerator

        data = request.get_json(silent=True) or {}
        topic = data.get("topic")

        generator = ExpertGenerator()
        content = generator.generate(topic=topic)

        if not content:
            return jsonify({"error": "Expert content generation failed"}), 500

        return jsonify({
            "message": "Expert content generated",
            "content": content.to_dict(),
        }), 201
    except Exception as exc:
        logger.exception("Error generating expert content: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ===================================================================
# App factory
# ===================================================================

def create_app(publish_queue: JsonPublishQueue) -> Flask:
    """Create and configure the Flask application.

    Args:
        publish_queue: A JsonPublishQueue instance to share across
                       all queue-related endpoints.

    Returns:
        Configured Flask app with all blueprints registered.
    """
    app = Flask(__name__)

    # Store shared objects in app config
    app.config["PUBLISH_QUEUE"] = publish_queue

    # Register blueprints
    app.register_blueprint(queue_bp)
    app.register_blueprint(competitors_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(expert_bp)

    # Health check endpoint
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})

    logger.info("Flask API server configured with all blueprints")
    return app


# ===================================================================
# Standalone entry point
# ===================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pq = JsonPublishQueue()
    app = create_app(publish_queue=pq)
    app.run(host="127.0.0.1", port=5000, debug=False)
