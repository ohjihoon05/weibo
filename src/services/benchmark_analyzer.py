"""Benchmark analyzer for competitor account analysis.

Collects competitor posts, analyzes engagement patterns, and
generates weekly benchmarking reports with actionable insights.
"""

import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from src.models.competitor import CompetitorAccount, CompetitorPost
from src.storage.json_store import (
    load_competitors,
    load_competitor_posts,
    append_competitor_posts,
    save_report,
    load_metrics,
    list_recent_posts,
)

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))


class BenchmarkAnalyzer:
    """Analyzes competitor accounts and generates benchmark reports."""

    def __init__(self, scraper=None):
        """Initialize with an optional WeiboScraper instance."""
        self._scraper = scraper

    def collect_competitor_posts(self) -> dict:
        """Scrape recent posts from all active competitors.

        Returns:
            Summary dict with counts per competitor.
        """
        if not self._scraper:
            logger.warning("No scraper configured for benchmark collection")
            return {}

        competitors = load_competitors()
        active = [c for c in competitors if c.get("active", True)]
        summary = {}

        for comp_data in active:
            uid = comp_data["uid"]
            nickname = comp_data.get("nickname", uid)
            try:
                posts = self._scraper.get_user_posts(uid, page=1)
                if posts:
                    post_dicts = [p.to_dict() for p in posts]
                    append_competitor_posts(post_dicts)
                    summary[nickname] = len(posts)
                    # Update last_scraped_at
                    comp_data["last_scraped_at"] = datetime.utcnow().isoformat()
                    logger.info("Collected %d posts from %s (%s)", len(posts), nickname, uid)
            except Exception as exc:
                logger.error("Failed to collect from %s (%s): %s", nickname, uid, exc)
                summary[nickname] = f"error: {exc}"

        # Save updated competitor data
        from src.storage.json_store import save_competitors
        save_competitors(competitors)

        return summary

    def generate_benchmark_report(self) -> dict:
        """Generate a weekly benchmarking report from collected data.

        Returns:
            Report dictionary with analysis results.
        """
        posts = load_competitor_posts()
        competitors = load_competitors()

        if not posts:
            return {"error": "No competitor data available"}

        # Filter to recent posts (last 7 days)
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        recent = [p for p in posts if p.get("scraped_at", "") >= cutoff]

        if not recent:
            recent = posts[-50:]  # Fallback to last 50 posts

        report = {
            "id": str(uuid.uuid4()),
            "period_start": cutoff[:10],
            "period_end": datetime.utcnow().strftime("%Y-%m-%d"),
            "competitors_analyzed": len(set(p.get("competitor_uid", "") for p in recent)),
            "total_posts_analyzed": len(recent),
            "top_posts": self._get_top_posts(recent, limit=10),
            "hashtag_analysis": self._analyze_hashtags(recent),
            "posting_pattern": self._analyze_posting_pattern(recent),
            "recommendations": self._generate_recommendations(recent),
            "created_at": datetime.utcnow().isoformat(),
        }

        # Save report
        save_report(report)
        logger.info("Benchmark report generated: %d posts analyzed", len(recent))
        return report

    def generate_weekly_report(self) -> dict:
        """Generate a weekly performance report for own posts.

        Returns:
            Report dict with performance summary.
        """
        metrics = load_metrics()
        posts = list_recent_posts(limit=20)

        if not posts:
            return {"error": "No posts available for report"}

        # Filter to last 7 days
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        recent_posts = [p for p in posts if p.get("created_at", "") >= cutoff]

        # Collect metrics for recent posts
        post_metrics = []
        for post in recent_posts:
            post_id = post.get("id", "")
            post_data = {
                "post_id": post_id,
                "text_preview": (post.get("formatted_text", "") or "")[:50],
                "created_at": post.get("created_at", ""),
                "weibo_url": post.get("weibo_url", ""),
            }

            # Find latest metrics for this post
            related_metrics = [m for m in metrics if m.get("post_id") == post_id]
            if related_metrics:
                latest = max(related_metrics, key=lambda m: m.get("collected_at", ""))
                post_data.update({
                    "reposts_count": latest.get("reposts_count", 0),
                    "comments_count": latest.get("comments_count", 0),
                    "attitudes_count": latest.get("attitudes_count", 0),
                    "total_engagement": (
                        latest.get("reposts_count", 0)
                        + latest.get("comments_count", 0)
                        + latest.get("attitudes_count", 0)
                    ),
                })
            else:
                post_data.update({
                    "reposts_count": 0,
                    "comments_count": 0,
                    "attitudes_count": 0,
                    "total_engagement": 0,
                })

            post_metrics.append(post_data)

        # Sort by engagement
        post_metrics.sort(key=lambda x: x["total_engagement"], reverse=True)

        report = {
            "type": "weekly_performance",
            "period_start": cutoff[:10],
            "period_end": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_posts": len(recent_posts),
            "posts": post_metrics,
            "avg_engagement": (
                sum(p["total_engagement"] for p in post_metrics) / len(post_metrics)
                if post_metrics else 0
            ),
            "created_at": datetime.utcnow().isoformat(),
        }

        return report

    def format_benchmark_telegram(self, report: dict) -> str:
        """Format a benchmark report for Telegram message."""
        lines = ["📊 주간 벤치마킹 리포트\n"]
        lines.append(f"기간: {report.get('period_start', '')} ~ {report.get('period_end', '')}")
        lines.append(f"분석 계정: {report.get('competitors_analyzed', 0)}개")
        lines.append(f"분석 포스트: {report.get('total_posts_analyzed', 0)}건\n")

        # Top posts
        top = report.get("top_posts", [])
        if top:
            lines.append("🏆 인기 포스트 TOP 5:")
            for i, post in enumerate(top[:5], 1):
                text = post.get("text_preview", "")[:30]
                eng = post.get("total_engagement", 0)
                lines.append(f"  {i}. [{eng}] {text}...")

        # Hashtags
        hashtags = report.get("hashtag_analysis", {}).get("top_hashtags", [])
        if hashtags:
            lines.append(f"\n#️⃣ 인기 해시태그:")
            lines.append("  " + ", ".join(f"#{h[0]}({h[1]})" for h in hashtags[:8]))

        # Posting pattern
        pattern = report.get("posting_pattern", {})
        peak_hours = pattern.get("peak_hours", [])
        if peak_hours:
            lines.append(f"\n⏰ 피크 시간대 (CST):")
            lines.append("  " + ", ".join(f"{h}시" for h in peak_hours[:3]))

        # Recommendations
        recs = report.get("recommendations", [])
        if recs:
            lines.append(f"\n💡 개선 제안:")
            for rec in recs[:3]:
                lines.append(f"  • {rec}")

        return "\n".join(lines)

    def format_weekly_telegram(self, report: dict) -> str:
        """Format a weekly performance report for Telegram."""
        lines = ["📈 주간 성과 리포트\n"]
        lines.append(f"기간: {report.get('period_start', '')} ~ {report.get('period_end', '')}")
        lines.append(f"발행 건수: {report.get('total_posts', 0)}건")
        lines.append(f"평균 인게이지먼트: {report.get('avg_engagement', 0):.1f}\n")

        posts = report.get("posts", [])
        if posts:
            lines.append("📑 포스트별 성과:")
            for i, p in enumerate(posts[:10], 1):
                text = p.get("text_preview", "")[:25]
                eng = p.get("total_engagement", 0)
                likes = p.get("attitudes_count", 0)
                comments = p.get("comments_count", 0)
                lines.append(f"  {i}. {text}...")
                lines.append(f"     ❤️{likes} 💬{comments} 합계:{eng}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private analysis methods
    # ------------------------------------------------------------------

    @staticmethod
    def _get_top_posts(posts: list[dict], limit: int = 10) -> list[dict]:
        """Get top posts by engagement."""
        for p in posts:
            p["total_engagement"] = (
                p.get("reposts_count", 0)
                + p.get("comments_count", 0)
                + p.get("attitudes_count", 0)
            )
            p["text_preview"] = (p.get("text", "") or "")[:50]

        sorted_posts = sorted(posts, key=lambda x: x["total_engagement"], reverse=True)
        return sorted_posts[:limit]

    @staticmethod
    def _analyze_hashtags(posts: list[dict]) -> dict:
        """Analyze hashtag frequency and effectiveness."""
        tag_counter = Counter()
        tag_engagement = {}

        for post in posts:
            hashtags = post.get("hashtags", [])
            engagement = (
                post.get("reposts_count", 0)
                + post.get("comments_count", 0)
                + post.get("attitudes_count", 0)
            )
            for tag in hashtags:
                tag_counter[tag] += 1
                if tag not in tag_engagement:
                    tag_engagement[tag] = []
                tag_engagement[tag].append(engagement)

        # Top hashtags by frequency
        top_hashtags = tag_counter.most_common(15)

        # Average engagement per hashtag
        tag_avg = {}
        for tag, engagements in tag_engagement.items():
            if engagements:
                tag_avg[tag] = sum(engagements) / len(engagements)

        # Top by avg engagement
        top_by_engagement = sorted(tag_avg.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "top_hashtags": top_hashtags,
            "top_by_engagement": top_by_engagement,
            "total_unique": len(tag_counter),
        }

    @staticmethod
    def _analyze_posting_pattern(posts: list[dict]) -> dict:
        """Analyze posting time patterns."""
        hour_counter = Counter()

        for post in posts:
            created = post.get("created_at", "")
            if not created:
                continue
            try:
                # Weibo created_at can be relative ("x分钟前") or absolute
                # We only parse ISO-like formats
                if "T" in created or "-" in created:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    cst_hour = (dt.hour + 8) % 24  # Rough CST conversion
                    hour_counter[cst_hour] += 1
            except (ValueError, AttributeError):
                continue

        # Peak hours
        peak_hours = [h for h, _ in hour_counter.most_common(5)]

        return {
            "hour_distribution": dict(hour_counter),
            "peak_hours": sorted(peak_hours),
            "total_analyzed": sum(hour_counter.values()),
        }

    @staticmethod
    def _generate_recommendations(posts: list[dict]) -> list[str]:
        """Generate actionable recommendations from analyzed data."""
        recs = []

        if not posts:
            return ["데이터가 부족합니다. 더 많은 경쟁 계정을 등록해주세요."]

        # Analyze top posts characteristics
        top = sorted(posts, key=lambda p: (
            p.get("reposts_count", 0) + p.get("comments_count", 0) + p.get("attitudes_count", 0)
        ), reverse=True)[:5]

        # Image count analysis
        avg_images = sum(p.get("image_count", 0) for p in top) / max(len(top), 1)
        if avg_images > 3:
            recs.append(f"인기 포스트 평균 이미지 수: {avg_images:.0f}장. 다양한 사진을 포함하세요.")

        # Text length analysis
        avg_len = sum(len(p.get("text", "")) for p in top) / max(len(top), 1)
        if avg_len > 100:
            recs.append(f"인기 포스트 평균 텍스트 길이: {avg_len:.0f}자. 상세한 설명이 효과적입니다.")
        else:
            recs.append("인기 포스트는 짧고 핵심적인 텍스트를 사용합니다.")

        # Hashtag analysis
        all_tags = []
        for p in top:
            all_tags.extend(p.get("hashtags", []))
        if all_tags:
            common = Counter(all_tags).most_common(3)
            tag_list = ", ".join(f"#{t}" for t, _ in common)
            recs.append(f"인기 해시태그: {tag_list}")

        return recs
