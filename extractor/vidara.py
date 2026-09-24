import re
from urllib.parse import urlparse

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


class VidaraExtractor(Extractor):

    name = "vidara"

    def can_handle(self, url):
        return "vidara.to" in url.lower()

    def extract(self, url):
        print(
            f"[EXTRACTOR:{self.name}] "
            f"Processing: {url}"
        )

        # --------------------------------------------------
        # Load Vidara page
        # --------------------------------------------------

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )

        response.raise_for_status()

        html = response.text

        print(
            f"[EXTRACTOR:{self.name}] "
            f"Vidara page loaded ({len(html)} bytes)"
        )

        # --------------------------------------------------
        # Find the embedded player URL
        # --------------------------------------------------

        player_match = re.search(
            r'<iframe[^>]+src=["\']'
            r'(https?://[^"\']+/e/([A-Za-z0-9_-]+))'
            r'["\']',
            html,
            re.IGNORECASE,
        )

        if not player_match:
            raise RuntimeError(
                "Could not find the embedded video player."
            )

        player_url = player_match.group(1)
        filecode = player_match.group(2)

        print(
            f"[EXTRACTOR:{self.name}] "
            f"Player URL: {player_url}"
        )

        print(
            f"[EXTRACTOR:{self.name}] "
            f"Filecode: {filecode}"
        )

        # --------------------------------------------------
        # Determine player origin
        # --------------------------------------------------

        parsed_player_url = urlparse(player_url)

        if not parsed_player_url.scheme or not parsed_player_url.netloc:
            raise RuntimeError(
                "Invalid embedded player URL."
            )

        player_origin = (
            f"{parsed_player_url.scheme}://"
            f"{parsed_player_url.netloc}"
        )

        api_url = (
            f"{player_origin}/api/stream"
        )

        print(
            f"[EXTRACTOR:{self.name}] "
            f"Stream API: {api_url}"
        )

        # --------------------------------------------------
        # Ask player site for stream information
        # --------------------------------------------------

        api_response = requests.post(
            api_url,
            headers={
                **HEADERS,
                "Content-Type": "application/json",
                "Referer": player_url,
                "Origin": player_origin,
            },
            json={
                "filecode": filecode,
                "device": "web",
            },
            timeout=20,
        )

        api_response.raise_for_status()

        try:
            stream_data = api_response.json()
        except ValueError as error:
            raise RuntimeError(
                "Player API returned invalid JSON."
            ) from error

        # --------------------------------------------------
        # Extract media URL
        # --------------------------------------------------

        streaming_url = stream_data.get(
            "streaming_url"
        )

        if not streaming_url:
            raise RuntimeError(
                "Player API did not return "
                "streaming_url."
            )

        # --------------------------------------------------
        # Extract title
        # --------------------------------------------------

        title = (
            stream_data.get("title")
            or filecode
            or "video"
        )

        print(
            f"[EXTRACTOR:{self.name}] "
            f"Title: {title}"
        )

        print(
            f"[EXTRACTOR:{self.name}] "
            f"Media URL resolved:"
        )

        print(streaming_url)

        # --------------------------------------------------
        # Return common extractor result
        # --------------------------------------------------

        return {
            "title": title,
            "media_url": streaming_url,
            "extension": "mp4",
        }