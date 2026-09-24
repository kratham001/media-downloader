from .vidara import VidaraExtractor
from .luluvid import LuluvidExtractor
from .generic import GenericExtractor


EXTRACTORS = [
    VidaraExtractor(),
    LuluvidExtractor(),
    GenericExtractor(),
]


def find_extractor(url):
    """
    Return the first extractor capable of handling the URL.
    """

    for extractor in EXTRACTORS:
        if extractor.can_handle(url):
            print(
                f"[EXTRACTOR] Selected: "
                f"{extractor.name}"
            )
            return extractor

    raise RuntimeError(
        "No extractor is available for this URL."
    )