import os

SERVER_HOST = "0.0.0.0"
SERVER_PORT = int(os.environ.get("PORT", 10000))

DOWNLOAD_DIR = os.path.join(
    os.getcwd(),
    "downloads"
)


