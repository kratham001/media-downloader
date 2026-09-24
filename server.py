import importlib
import os
import threading
import uuid

from flask import (
    Flask,
    jsonify,
    request,
    send_from_directory,
)
from flask_cors import CORS

from config import (
    SERVER_HOST,
    SERVER_PORT,
    DOWNLOAD_DIR,
)

from core import (
    download_media,
    get_download_path,
    make_unique_filename,
)

from extractor import find_extractor


app = Flask(__name__)
CORS(app)


DOWNLOAD_DIR = os.path.abspath(
    DOWNLOAD_DIR
)


JOBS = {}


def extraction_and_download_worker(
    job_id,
    extracted,
    filename,
):
    try:
        JOBS[job_id]["status"] = "downloading"
        JOBS[job_id]["message"] = (
            "Downloading media..."
        )

        output_path = get_download_path(
            filename
        )

        download_media(
            extracted["media_url"],
            output_path,
        )

        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["message"] = (
            "Download completed."
        )

        JOBS[job_id]["download_url"] = (
            f"/files/{filename}"
        )

        print(
            f"[SUCCESS] Job {job_id}: "
            f"{filename}"
        )

    except Exception as error:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["message"] = str(error)

        print(
            f"[ERROR] Job {job_id}: "
            f"{type(error).__name__}: "
            f"{error}"
        )


@app.route(
    "/download",
    methods=["POST"],
)
def download():
    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    media_url = data.get("url")

    if not media_url:
        return jsonify({
            "status": "error",
            "message": (
                "No target URL provided."
            ),
        }), 400

    job_id = uuid.uuid4().hex[:12]

    JOBS[job_id] = {
        "status": "extracting",
        "message": "Finding media...",
    }

    try:
        extractor = find_extractor(
            media_url
        )

        JOBS[job_id]["extractor"] = (
            extractor.name
        )

        print(
            f"[JOB {job_id}] "
            f"Using extractor: "
            f"{extractor.name}"
        )

        extracted = extractor.extract(
            media_url
        )

        title = (
            extracted.get("title")
            or "video"
        )

        extension = (
            extracted.get("extension")
            or "mp4"
        )

        filename = make_unique_filename(
            title,
            extension,
        )

        JOBS[job_id].update({
            "title": title,
            "filename": filename,
            "status": "queued",
            "message": (
                "Media found. "
                "Download starting..."
            ),
        })

        thread = threading.Thread(
            target=(
                extraction_and_download_worker
            ),
            args=(
                job_id,
                extracted,
                filename,
            ),
            daemon=True,
        )

        thread.start()

        return jsonify({
            "status": "started",
            "id": job_id,
            "title": title,
            "filename": filename,
            "download_url": (
                f"/files/{filename}"
            ),
            "status_url": (
                f"/status/{job_id}"
            ),
            "extractor": extractor.name,
        }), 202

    except Exception as error:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["message"] = str(error)

        print(
            f"[ERROR] Job {job_id}: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return jsonify({
            "status": "error",
            "id": job_id,
            "message": str(error),
        }), 500


@app.route(
    "/status/<job_id>",
    methods=["GET"],
)
def job_status(job_id):
    job = JOBS.get(job_id)

    if not job:
        return jsonify({
            "status": "error",
            "message": "Job not found.",
        }), 404

    response = {
        "status": job.get("status"),
        "message": job.get("message"),
        "title": job.get("title"),
        "filename": job.get("filename"),
        "extractor": job.get("extractor"),
        "download_url": job.get(
            "download_url"
        ),
    }

    return jsonify(response)


@app.route(
    "/files/<path:filename>",
    methods=["GET", "HEAD"],
)
def download_file(filename):
    try:
        file_path = get_download_path(
            filename
        )
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "Invalid filename.",
        }), 400

    if not os.path.isfile(file_path):
        return jsonify({
            "status": "error",
            "message": "File not found.",
        }), 404

    return send_from_directory(
        DOWNLOAD_DIR,
        filename,
        as_attachment=True,
    )


if __name__ == "__main__":
    app.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        debug=True,
    )