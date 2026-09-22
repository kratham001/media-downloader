import os
import re
import threading
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Persistent storage folder in the host environment
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def target_extractor_pipeline(webpage_url):
    print(f"📡 Processing target link: {webpage_url}")
    
    # Masquerade as a desktop browser to prevent basic scraping walls
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    # Normalize video pathways to embed player configurations
    if "vidara.to" in webpage_url and "/v/" in webpage_url:
        webpage_url = webpage_url.replace("/v/", "/e/")
    if "luluvid.com" in webpage_url and "/v/" in webpage_url:
        webpage_url = webpage_url.replace("/v/", "/e/")

    try:
        # Fetch the underlying page source
        response = requests.get(webpage_url, headers=headers, timeout=15)
        html_source = response.text

        # Regex Scan: Pinpoint the raw media URL stream (matches file properties or standalone stream paths)
        media_match = re.search(r'(?:file|source|src)\s*:\s*["\'](https?://[^"\']+\.(?:mp4|m3u8|webm)[^"\']*)["\']', html_source, re.IGNORECASE)
        
        # Fallback broad match if the player uses strict variable packaging
        if not media_match:
            media_match = re.search(r'["\'](https?://[^"\']+\.(?:mp4|m3u8|webm)[^"\']*)["\']', html_source, re.IGNORECASE)

        if not media_match:
            print("❌ Failed to isolate media signatures inside page layout structure.")
            return

        resolved_stream_url = media_match.group(1)
        print(f"🎯 Resource Located: {resolved_stream_url}")

        # Derive a clean filename from the request path
        filename = webpage_url.split('/')[-1].split('?')[0] + ".mp4"
        output_filepath = os.path.join(DOWNLOAD_DIR, filename)

        # Download the file block-by-block to preserve operational memory
        print(f"⏳ Downloading media chunk stream down to: {output_filepath}")
        with requests.get(resolved_stream_url, headers=headers, stream=True, timeout=60) as video_stream:
            video_stream.raise_for_status()
            with open(output_filepath, 'wb') as local_file:
                for data_chunk in video_stream.iter_content(chunk_size=8192):
                    if data_chunk:
                        local_file.write(data_chunk)
                        
        print(f"✅ Securely downloaded: {filename}")

    except Exception as error:
        print(f"❌ Core processing error: {error}")

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    media_url = data.get('url')
    if not media_url:
        return jsonify({"status": "error", "message": "No target URL provided"}), 400

    # Execute in background thread so cloud routes don't freeze or timeout
    threading.Thread(target=target_extractor_pipeline, args=(media_url,)).start()
    return jsonify({"status": "success", "message": "Extraction pipeline triggered successfully!"})

@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "active"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
