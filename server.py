import os
import re
import shutil
import subprocess
import threading
import uuid

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from config import (
    SERVER_HOST,
    SERVER_PORT,
    DOWNLOAD_DIR,
)


DOWNLOAD_DIR = os.path.abspath(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


app = Flask(__name__)
CORS(app)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def make_safe_filename(name):
    name = re.sub(
        r'[<>:"/\\|?*\x00-\x1F]',
        "_",
        str(name)
    ).strip()

    return name or "video"


def extract_vidara(webpage_url):
    print(f"[REQUEST] {webpage_url}")

    response = requests.get(
        webpage_url,
        headers=HEADERS,
        timeout=20
    )
    response.raise_for_status()

    html = response.text

    print(f"[FETCH] Vidara page loaded ({len(html)} bytes)")

    viderea_match = re.search(
        r'https?://viderea\.site/e/([A-Za-z0-9_-]+)',
        html,
        re.IGNORECASE
    )

    if not viderea_match:
        raise RuntimeError(
            "Could not find the Viderea player."
        )

    filecode = viderea_match.group(1)

    print(f"[EXTRACTOR] Viderea filecode: {filecode}")

    api_response = requests.post(
        "https://viderea.site/api/stream",
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

    streaming_url = stream_data.get("streaming_url")

    if not streaming_url:
        raise RuntimeError(
            "Viderea API did not return streaming_url."
        )

    title = make_safe_filename(
        stream_data.get("title", filecode)
    )

    print("[MEDIA] Streaming URL resolved:")
    print(streaming_url)

    return {
        "filecode": filecode,
        "title": title,
        "streaming_url": streaming_url,
    }


def download_media(streaming_url, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if ".m3u8" in streaming_url:
        print("[MEDIA] HLS playlist detected.")
        print(f"[FFMPEG] Saving to: {output_path}")

        result = subprocess.run([
            "ffmpeg",
            "-y",
            "-i", streaming_url,
            "-c", "copy",
            output_path
        ])

        if result.returncode != 0:
            raise RuntimeError("FFmpeg failed to download the HLS stream.")

    else:
        print("[MEDIA] Direct media detected.")
        print(f"[DOWNLOAD] Saving to: {output_path}")

        with requests.get(streaming_url, stream=True, timeout=60) as response:
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

    if not os.path.isfile(output_path):
        raise RuntimeError("Download completed but output file was not created.")

    size = os.path.getsize(output_path)

    if size == 0:
        raise RuntimeError("Downloaded file is empty.")

    print(f"[SUCCESS] Downloaded {size / (1024 * 1024):.2f} MB")


def extraction_worker(webpage_url, filename):

    try:

        extracted = extract_vidara(webpage_url)

        output_path = os.path.join(
            DOWNLOAD_DIR,
            filename
        )

        download_media(
            extracted["streaming_url"],
            output_path
        )

        print(
            f"[SUCCESS] File ready: {filename}"
        )

    except Exception as error:

        print(
            f"[ERROR] {type(error).__name__}: {error}"
        )


@app.route("/download", methods=["POST"])
def download():

    data = request.get_json(silent=True) or {}

    media_url = data.get("url")

    if not media_url:
        return jsonify({
            "status": "error",
            "message": "No target URL provided."
        }), 400

    if "vidara.to" not in media_url.lower():
        return jsonify({
            "status": "error",
            "message": "Vidara is currently the only supported site."
        }), 400

    job_id = uuid.uuid4().hex[:12]

    filename = f"{job_id}.mp4"

    thread = threading.Thread(
        target=extraction_worker,
        args=(media_url, filename),
        daemon=True
    )

    thread.start()

    return jsonify({
        "status": "started",
        "id": job_id,
        "filename": filename,
        "download_url": f"/files/{filename}",
    }), 202


@app.route("/files/<filename>", methods=["GET", "HEAD"])
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_DIR, filename)

    if not os.path.isfile(file_path):
        return jsonify({
            "error": "File not ready",
            "filename": filename
        }), 404

    return send_from_directory(
        DOWNLOAD_DIR,
        filename,
        as_attachment=True
    )


@app.route("/", methods=["GET"])
def health():

    return jsonify({
        "status": "active",
        "service": "media-downloader"
    })


if __name__ == "__main__":

    print("----------------------------------------")
    print(" Media Downloader")
    print("----------------------------------------")
    print(f" Server: {SERVER_HOST}:{SERVER_PORT}")
    print(f" Downloads: {DOWNLOAD_DIR}")
    print("----------------------------------------")

    app.run(
        host=SERVER_HOST,
        port=SERVER_PORT
    )