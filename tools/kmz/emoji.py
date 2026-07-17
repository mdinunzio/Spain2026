"""Render emoji to PNG pin icons using Twemoji, with a local cache.

Google My Maps cannot draw emoji glyphs as pins, so each emoji is baked into
a PNG that ships inside the KMZ. Twemoji gives identical, colorful artwork on
every OS (unlike rendering with whatever emoji font the local machine has).
"""

import urllib.error
import urllib.request
from pathlib import Path

from tools.kmz.exceptions import EmojiRenderError

# jdecked's actively-maintained Twemoji fork; 72x72 is the largest raster set.
TWEMOJI_CDN = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72"
VARIATION_SELECTOR = "fe0f"
KEYCAP = "20e3"


def get_twemoji_basename(emoji: str) -> str:
    """Return the Twemoji filename stem for an emoji.

    Twemoji drops the U+FE0F variation selector from filenames except in
    keycap sequences, and joins the remaining codepoints with hyphens.

    Args:
        emoji: A single emoji, possibly multi-codepoint.

    Returns:
        The lowercase, hyphen-joined codepoint stem (no extension).
    """
    codepoints = [f"{ord(char):x}" for char in emoji]
    if VARIATION_SELECTOR in codepoints and KEYCAP not in codepoints:
        codepoints = [cp for cp in codepoints if cp != VARIATION_SELECTOR]
    return "-".join(codepoints)


def get_icon_filename(emoji: str) -> str:
    """Return the in-KMZ filename for an emoji's pin icon."""
    return f"{get_twemoji_basename(emoji)}.png"


def fetch_emoji_png(emoji: str, cache_dir: Path) -> bytes:
    """Fetch (or load from cache) the Twemoji PNG bytes for an emoji.

    Args:
        emoji: A single emoji to render.
        cache_dir: Directory used to cache downloaded PNGs across runs.

    Returns:
        The PNG file contents.

    Raises:
        EmojiRenderError: If the emoji has no Twemoji asset or the download
            fails and nothing is cached.
    """
    filename = get_icon_filename(emoji)
    cached = cache_dir / filename
    if cached.exists():
        return cached.read_bytes()

    url = f"{TWEMOJI_CDN}/{filename}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise EmojiRenderError(
                f"No Twemoji asset for {emoji!r} (tried {filename}). "
                "Pick a more common emoji for this venue."
            ) from error
        raise EmojiRenderError(f"Failed to fetch {url}: {error}") from error
    except urllib.error.URLError as error:
        raise EmojiRenderError(
            f"Could not reach the Twemoji CDN for {emoji!r}: {error}. "
            "Connect once to warm the icon cache, then re-run offline."
        ) from error

    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


def render_icons(emojis: set[str], cache_dir: Path) -> dict[str, tuple[str, bytes]]:
    """Render a set of emojis to pin icons.

    Args:
        emojis: The unique emojis to render.
        cache_dir: Directory used to cache downloaded PNGs across runs.

    Returns:
        Mapping of emoji -> (in-KMZ filename, PNG bytes).
    """
    icons = {}
    for emoji in sorted(emojis):
        icons[emoji] = (get_icon_filename(emoji), fetch_emoji_png(emoji, cache_dir))
    return icons
