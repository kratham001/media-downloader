from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import threading

app = Flask(__name__)
# Enable CORS so your browser User Script is allowed to talk to this local server
CORS(app)

def run_downloader(media_url):
    ydl_opts = {
        # Removed the broken local browser cookie check for the cloud environment
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': 'downloads/%(title)s_%(id)s.%(ext)s',
        
        # Force yt-dlp to accept and try processing generic embedded frames
        'allow_unplayable_formats': True,
        'ignoreerrors': False,
        
        # Emulate a clean desktop browser to avoid getting served generic 403 walls
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://vidara.to/',
        }
    }
    try:
        # Optimization: If it's a Vidara page link (/v/), automatically test the underlying player embed (/e/) 
        if "/v/" in media_url:
            media_url = media_url.replace("/v/", "/e/")
            
        print(f"📡 Extracting optimized stream target: {media_url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([media_url])
        print("✅ Download and stitching complete!")
    except Exception as e:
        print(f"❌ Error downloading asset: {e}")


@app.route('/download', methods=['POST'])
def download():
    data = request.json
    media_url = data.get('url')
    
    if not media_url:
        return jsonify({"status": "error", "message": "No media URL provided"}), 400

    # Run downloader in a background thread so the browser script doesn't freeze or timeout
    threading.Thread(target=run_downloader, args=(media_url,)).start()
    
    return jsonify({"status": "success", "message": "Extraction started in background!"})

if __name__ == '__main__':
    # Start local micro-server on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
