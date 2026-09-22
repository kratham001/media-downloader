from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import threading

app = Flask(__name__)
# Enable CORS so your browser User Script is allowed to talk to this local server
CORS(app)

def run_downloader(media_url):
    ydl_opts = {
        # Dynamically grabs active session tokens/cookies from Chrome to bypass paywalls
        'cookiesfrombrowser': ('chrome',), 
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': 'downloads/%(title)s_%(id)s.%(ext)s',
    }
    try:
        print(f"📡 Extracting specific stream: {media_url}")
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
