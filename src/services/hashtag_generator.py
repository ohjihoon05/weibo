"""Hashtag generator for Weibo posts based on PropertyListing fields.

Produces a deduplicated list of Chinese hashtags covering base tags,
location, property type, and investment indicators.
"""

from src.models.property_listing import PropertyListing

# Ordered: longer/more-specific keys first to avoid substring false matches
# (e.g. "京都" must not match inside "東京都")
PREFECTURE_HASHTAGS = [
    ("東京都", "#东京房产"),
    ("東京", "#东京房产"),
    ("东京", "#东京房产"),
    ("北海道", "#北海道房产"),
    ("名古屋", "#名古屋房产"),
    ("大阪", "#大阪房产"),
    ("京都", "#京都房产"),
    ("横浜", "#横滨房产"),
    ("横滨", "#横滨房产"),
    ("福岡", "#福冈房产"),
    ("福冈", "#福冈房产"),
    ("札幌", "#札幌房产"),
    ("神戸", "#神户房产"),
    ("神户", "#神户房产"),
    ("沖縄", "#冲绳房产"),
    ("冲绳", "#冲绳房产"),
]


def generate_hashtags(listing: PropertyListing) -> list[str]:
    """Generate a deduplicated list of Chinese hashtags for a property listing.

    Hashtag categories:
        1. Base hashtags (always included)
        2. Location-based (matched from listing.location)
        3. Type-based (matched from listing.layout and listing.structure)
        4. Investment-based (present when yield data exists)

    Args:
        listing: A PropertyListing with populated fields.

    Returns:
        A deduplicated list of hashtag strings.
    """
    seen: set[str] = set()
    hashtags: list[str] = []

    def _add(tag: str) -> None:
        if tag not in seen:
            seen.add(tag)
            hashtags.append(tag)

    # 1. Base hashtags (always included)
    for tag in ["#日本房产", "#日本不动产", "#海外投资"]:
        _add(tag)

    # 2. Location-based hashtags
    #    Match longer keys first; once a tag is added, consume the matched
    #    substring to prevent shorter keys from false-matching within it.
    if listing.location:
        remaining = listing.location
        for key, tag in PREFECTURE_HASHTAGS:
            if key in remaining:
                _add(tag)
                remaining = remaining.replace(key, "", 1)

    # 3. Type-based hashtags
    layout = listing.layout or ""
    structure = listing.structure or ""

    # If layout contains "1" (1R, 1K, 1LDK etc)
    if "1" in layout:
        _add("#单身公寓")

    # If structure contains wood indicators
    if "木造" in structure or "木" in structure:
        _add("#一户建")

    # If structure contains RC/SRC/mansion indicators
    if "RC" in structure or "SRC" in structure or "マンション" in structure:
        _add("#公寓")

    # 4. Investment-based hashtag
    if listing.yield_gross is not None:
        _add("#投资回报")

    return hashtags
