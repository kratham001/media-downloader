import re
from urllib.parse import urljoin

import requests

from .base import Extractor


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


class GenericExtractor(Extractor):
    name = "generic"

    def can_handle(self, url):
        return True

    def extract(self, url):
        print(
            f"[EXTRACTOR:{self.name}] "
            f"Trying generic extraction: {url}"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )
        response.raise_for_status()

        html = response.text

        title = self._extract_title(html)

        media_url = self._extract_media_url(
            html,
            url,
        )

        if not media_url:
            raise RuntimeError(
                "Generic extractor could not find a media URL."
            )

        extension = "mp4"

        if ".m3u8" in media_url.lower():
            extension = "mp4"
        elif ".webm" in media_url.lower():
            extension = "webm"

        return {
            "title": title or "video",
            "media_url": media_url,
            "extension": extension,
        }

    @staticmethod
    def _extract_title(html):
        patterns = [
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title',
            r"<title[^>]*>(.*?)</title>",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                html,
                re.IGNORECASE | re.DOTALL,
            )

            if match:
                title = match.group(1)

                title = re.sub(
                    r"\s+",
                    " ",
                    title,
                ).strip()

                if title:
                    return title

        return None

    @staticmethod
    def _extract_media_url(html, page_url):
        patterns = [
            r'<meta[^>]+property=["\']og:video(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:video(?::secure_url)?["\']',
            r'<video[^>]+src=["\']([^"\']+)',
            r'<source[^>]+src=["\']([^"\']+)',
            r'https?://[^"\']+\.m3u8(?:\?[^"\']*)?',
            r'https?://[^"\']+\.mp4(?:\?[^"\']*)?',
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                html,
                re.IGNORECASE,
            )

            if match:
                media_url = match.group(1)

                return urljoin(
                    page_url,
                    media_url,
                )

        return None