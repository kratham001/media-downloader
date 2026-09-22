import os
import re
import threading
import requests
import subprocess
import shutil

from flask import Flask, request, jsonify
from flask_cors import CORS


app = Flask(__name__)
CORS(app)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


# ---------------------------------------------------------
# Vidara / Viderea extractor
# ---------------------------------------------------------

def extract_vidara(webpage_url):
    print(f"[REQUEST] {webpage_url}")

    # -----------------------------------------------------
    # 1. Get the Vidara page
    # -----------------------------------------------------

    response = requests.get(
        webpage_url,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    html = response.text

    print(f"[FETCH] Vidara page loaded ({len(html)} bytes)")


    # -----------------------------------------------------
    # 2. Find the Viderea embed
    # -----------------------------------------------------

    viderea_match = re.search(
        r'https?://viderea\.site/e/([A-Za-z0-9_-]+)',
        html,
        re.IGNORECASE
    )

    if not viderea_match:
        raise RuntimeError(
            "Could not find the Viderea player inside the Vidara page."
        )

    filecode = viderea_match.group(1)

    print(f"[EXTRACTOR] Viderea filecode: {filecode}")


    # -----------------------------------------------------
    # 3. Ask Viderea for the stream information
    #
    # The Viderea player source we inspected does:
    #
    # POST /api/stream
    #
    # {
    #     "filecode": "...",
    #     "device": "web"
    # }
    # -----------------------------------------------------

    stream_api = "https://viderea.site/api/stream"

    print("[API] Requesting Viderea stream information...")

    api_response = requests.post(
        stream_api,
        headers={
            **HEADERS,
            "Content-Type": "application/json",
            "Referer": f"https://viderea.site/e/{filecode}",
            "Origin": "https://viderea.site",
        },
        json={
            "filecode": filecode,
            "device": "web",
        },
        timeout=20
    )

    api_response.raise_for_status()

    stream_data = api_response.json()

    print("[API] Stream response received")


    # -----------------------------------------------------
    # 4. Extract streaming_url
    # -----------------------------------------------------

    streaming_url = stream_data.get("streaming_url")

    if not streaming_url:
        raise RuntimeError(
            f"Viderea API did not return streaming_url. "
            f"Response keys: {list(stream_data.keys())}"
        )

    print(f"[MEDIA] Streaming URL resolved:")
    print(streaming_url)


    # -----------------------------------------------------
    # 5. Get title if the API provides one
    # -----------------------------------------------------

    title = stream_data.get("title")

    if not title:
        title = filecode

    # Remove characters that are unsafe in filenames
    safe_title = re.sub(
        r'[<>:"/\\|?*\x00-\x1F]',
        "_",
        str(title)
    ).strip()

    if not safe_title:
        safe_title = filecode


    # -----------------------------------------------------
    # 6. Determine media type
    # -----------------------------------------------------

    lower_url = streaming_url.lower()

    if ".m3u8" in lower_url:
        media_type = "m3u8"
        extension = ".m3u8"

    elif ".webm" in lower_url:
        media_type = "webm"
        extension = ".webm"

    elif ".mp4" in lower_url:
        media_type = "mp4"
        extension = ".mp4"

    else:
        media_type = "unknown"
        extension = ".bin"


    print(f"[MEDIA] Detected type: {media_type}")


    # -----------------------------------------------------
    # 7. For this first test:
    #
    #    Only download direct files.
    #
    #    We deliberately DON'T pretend an m3u8 playlist
    #    is an MP4. We'll add proper HLS handling after
    #    the first extraction test succeeds.
    # -----------------------------------------------------

    if media_type == "m3u8":
        if not shutil.which("ffmpeg"):
            raise RuntimeError("FFmpeg is not installed or not available in PATH")
    
        output_filepath = os.path.join(
            DOWNLOAD_DIR,
            f"{safe_title}.mp4"
        )
    
        print("[MEDIA] HLS playlist detected.")
        print(f"[FFMPEG] Saving to: {output_filepath}")
    
        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-i",
            streaming_url,
            "-c",
            "copy",
            output_filepath,
        ]
    
        result = subprocess.run(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    
        if result.returncode != 0:
            print("[FFMPEG] Download failed")
            print(result.stderr)
            raise RuntimeError(
                f"FFmpeg failed with exit code {result.returncode}"
            )
    
        print(f"[SUCCESS] Downloaded: {output_filepath}")
    
        return {
            "status": "downloaded",
            "filecode": filecode,
            "title": title,
            "media_type": "m3u8",
            "output_file": output_filepath,
            "message": "HLS stream downloaded successfully."
        }


    # -----------------------------------------------------
    # 8. Download direct MP4/WebM
    # -----------------------------------------------------

    output_filename = safe_title + extension
    output_filepath = os.path.join(
        DOWNLOAD_DIR,
        output_filename
    )

    print(f"[DOWNLOAD] Saving to: {output_filepath}")

    with requests.get(
        streaming_url,
        headers={
            **HEADERS,
            "Referer": f"https://viderea.site/e/{filecode}",
            "Origin": "https://viderea.site",
        },
        stream=True,
        timeout=60
    ) as media_response:

        media_response.raise_for_status()

        total_bytes = 0

        with open(output_filepath, "wb") as output_file:

            for chunk in media_response.iter_content(
                chunk_size=1024 * 1024
            ):

                if not chunk:
                    continue

                output_file.write(chunk)
                total_bytes += len(chunk)


    print(
        f"[DOWNLOAD] Complete: "
        f"{total_bytes / (1024 * 1024):.2f} MB"
    )

    return {
        "status": "completed",
        "filecode": filecode,
        "title": safe_title,
        "media_type": media_type,
        "streaming_url": streaming_url,
        "filename": output_filename,
        "filepath": output_filepath,
        "size_bytes": total_bytes,
    }


# ---------------------------------------------------------
# Background worker
# ---------------------------------------------------------

def extraction_worker(webpage_url):
    try:
        result = extract_vidara(webpage_url)

        print("[SUCCESS]")
        print(result)

    except Exception as error:
        print(f"[ERROR] {type(error).__name__}: {error}")


# ---------------------------------------------------------
# API endpoint
# ---------------------------------------------------------

@app.route("/download", methods=["POST"])
def download():

    data = request.get_json(silent=True) or {}

    media_url = data.get("url")

    if not media_url:
        return jsonify({
            "status": "error",
            "message": "No target URL provided"
        }), 400


    # Currently this endpoint is intentionally focused
    # on Vidara testing.

    if "vidara.to" not in media_url.lower():
        return jsonify({
            "status": "error",
            "message": "This test version currently supports Vidara only."
        }), 400


    # Start extraction in background
    thread = threading.Thread(
        target=extraction_worker,
        args=(media_url,),
        daemon=True
    )

    thread.start()


    return jsonify({
        "status": "started",
        "message": "Vidara extraction started."
    }), 202


# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------

@app.route("/", methods=["GET"])
def health():

    return jsonify({
        "status": "active",
        "service": "media extractor"
    }), 200


# ---------------------------------------------------------
# Start server
# ---------------------------------------------------------

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 10000)
    )

    print("----------------------------------------")
    print(" Media Extractor")
    print("----------------------------------------")
    print(f" Server running on port {port}")
    print(f" Downloads: {DOWNLOAD_DIR}")
    print("----------------------------------------")

    app.run(
        host="0.0.0.0",
        port=port
    )

