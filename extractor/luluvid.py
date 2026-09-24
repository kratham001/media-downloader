from .base import Extractor


class LuluvidExtractor(Extractor):
    name = "luluvid"

    def can_handle(self, url):
        return "luluvid" in url.lower()

    def extract(self, url):
        raise RuntimeError(
            "Luluvid extractor is not implemented yet."
        )