import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import DOWNLOAD_DIR


DOWNLOAD_DIR = os.path.abspath(DOWNLOAD_DIR)

os.makedirs(
    DOWNLOAD_DIR,
    exist_ok=True,
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def make_safe_filename(name):
    """
    Convert a media title into a filesystem-safe filename.
    """

    name = str(name or "").strip()

    name = re.sub(
        r'[<>:"/\\|?*\x00-\x1F]',
        "_",
        name,
    )

    name = re.sub(
        r"\s+",
        " ",
        name,
    ).strip()

    name = name.rstrip(".")

    if not name:
        name = "video"

    return name


def make_unique_filename(
    title,
    extension="mp4",
):
    """
    Return a filename that does not collide with an existing file.

    Example:

        My Video.mp4
        My Video (1).mp4
        My Video (2).mp4
    """

    safe_title = make_safe_filename(title)

    extension = extension.lstrip(".")

    base = f"{safe_title}.{extension}"

    candidate = os.path.join(
        DOWNLOAD_DIR,
        base,
    )

    counter = 1

    while os.path.exists(candidate):
        base = (
            f"{safe_title} "
            f"({counter})."
            f"{extension}"
        )

        candidate = os.path.join(
            DOWNLOAD_DIR,
            base,
        )

        counter += 1

    return base


def _temporary_output_path(output_path):
    return output_path[:-4] + ".part.mp4"


def download_media(
    media_url,
    output_path,
):
    """
    Download media into a temporary file and only expose
    the final filename after successful completion.
    """

    output_path = os.path.abspath(output_path)

    os.makedirs(
        os.path.dirname(output_path),
        exist_ok=True,
    )

    temp_path = _temporary_output_path(
        output_path
    )

    print(
        f"[DOWNLOAD] Temporary file: "
        f"{temp_path}"
    )

    try:
        if ".m3u8" in media_url.lower():
            _download_hls(
                media_url,
                temp_path,
            )
        else:
            _download_direct(
                media_url,
                temp_path,
            )

        validate_media(
            temp_path
        )

        size = os.path.getsize(
            temp_path
        )

        if size <= 0:
            raise RuntimeError(
                "Downloaded file is empty."
            )

        os.replace(
            temp_path,
            output_path,
        )

        print(
            f"[SUCCESS] Downloaded "
            f"{size / (1024 * 1024):.2f} MB"
        )

        print(
            f"[SUCCESS] Final file: "
            f"{output_path}"
        )

    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        raise


def _download_hls(
    media_url,
    output_path,
):
    print("[MEDIA] HLS playlist detected.")

    command = [
        "ffmpeg",
        "-y",
        "-i",
        media_url,
        "-c",
        "copy",
        "-f",
        "mp4",
        output_path,
    ]

    print(
        "[FFMPEG] Starting HLS download..."
    )

    result = subprocess.run(
        command
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg failed to download "
            "the HLS stream."
        )


def _download_direct(
    media_url,
    output_path,
):
    print(
        "[MEDIA] Direct media detected."
    )

    with requests.get(
        media_url,
        headers=HEADERS,
        stream=True,
        timeout=60,
    ) as response:

        response.raise_for_status()

        with open(
            output_path,
            "wb",
        ) as file:

            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    file.write(chunk)


def validate_media(path):
    """
    Use ffprobe to verify that FFmpeg actually produced
    a readable media file.
    """

    if not os.path.isfile(path):
        raise RuntimeError(
            "Media file was not created."
        )

    if os.path.getsize(path) == 0:
        raise RuntimeError(
            "Media file is empty."
        )

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=format_name,duration",
        "-of",
        "default=noprint_wrappers=1",
        path,
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Downloaded media failed validation:\n"
            + result.stderr.strip()
        )

    print(
        "[VALIDATION] Media file passed ffprobe."
    )


def get_download_path(
    filename,
):
    """
    Safely construct a path inside DOWNLOAD_DIR.
    """

    download_dir = Path(
        DOWNLOAD_DIR
    ).resolve()

    candidate = (
        download_dir / filename
    ).resolve()

    if download_dir not in candidate.parents:
        raise ValueError(
            "Invalid download filename."
        )

    return str(candidate)