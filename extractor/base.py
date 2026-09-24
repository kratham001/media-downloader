class Extractor:
    name = "base"

    def can_handle(self, url):
        """
        Return True if this extractor knows how to handle the URL.
        """
        raise NotImplementedError

    def extract(self, url):
        """
        Return a dictionary containing at least:

            {
                "title": "Video title",
                "media_url": "https://example.com/video.m3u8",
                "extension": "mp4",
            }

        """
        raise NotImplementedError