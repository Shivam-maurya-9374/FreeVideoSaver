from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
import requests
from urllib.parse import urlparse
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# CORS enabled for all domains
CORS(app)

# Ensure download directory exists
if not os.path.exists(app.config['DOWNLOAD_FOLDER']):
    os.makedirs(app.config['DOWNLOAD_FOLDER'])

# Cleanup function to remove old files
def cleanup_old_files():
    while True:
        try:
            now = time.time()
            for filename in os.listdir(app.config['DOWNLOAD_FOLDER']):
                file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
                if os.path.isfile(file_path):
                    # Delete files older than 1 hour
                    if now - os.path.getctime(file_path) > 3600:
                        os.remove(file_path)
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        # Run cleanup every 30 minutes
        time.sleep(1800)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

def is_supported_url(url):
    """Check if the URL is from a supported domain"""
    supported_domains = [
        'youtube.com', 'youtu.be', 
        'facebook.com', 'fb.watch',
        'instagram.com', 'instagr.am',
        'twitter.com', 't.co',
        'tiktok.com', 'vm.tiktok.com',
        'vimeo.com', 'dailymotion.com',
        'reddit.com', 'soundcloud.com'
    ]
    
    try:
        domain = urlparse(url).netloc.lower()
        return any(supported_domain in domain for supported_domain in supported_domains)
    except:
        return False

def get_video_info(url):
    """Get video information using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown Title'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'formats': info.get('formats', [])
            }
    except Exception as e:
        print(f"Error getting video info: {e}")
        return None

def download_video(url, format_id='best'):
    """Download video using yt-dlp"""
    # Generate unique filename
    filename = f"{str(uuid.uuid4())}.mp4"
    filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
    
    ydl_opts = {
        'outtmpl': filepath,
        'format': format_id,
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return filepath
    except Exception as e:
        print(f"Download error: {e}")
        # Clean up if file was partially downloaded
        if os.path.exists(filepath):
            os.remove(filepath)
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    """API endpoint to get video information"""
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({'success': False, 'message': 'No URL provided'})
    
    url = data['url'].strip()
    
    if not url:
        return jsonify({'success': False, 'message': 'URL is empty'})
    
    if not is_supported_url(url):
        return jsonify({'success': False, 'message': 'Unsupported URL or domain'})
    
    video_info = get_video_info(url)
    
    if not video_info:
        return jsonify({'success': False, 'message': 'Could not retrieve video information'})
    
    return jsonify({
        'success': True,
        'title': video_info['title'],
        'duration': video_info['duration'],
        'thumbnail': video_info['thumbnail'],
    })

@app.route('/api/download', methods=['POST'])
def download():
    """API endpoint to download video"""
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({'success': False, 'message': 'No URL provided'})
    
    url = data['url'].strip()
    format_id = data.get('format', 'best')
    
    if not url:
        return jsonify({'success': False, 'message': 'URL is empty'})
    
    if not is_supported_url(url):
        return jsonify({'success': False, 'message': 'Unsupported URL or domain'})
    
    filepath = download_video(url, format_id)
    
    if not filepath or not os.path.exists(filepath):
        return jsonify({'success': False, 'message': 'Download failed'})
    
    filename = os.path.basename(filepath)
    return jsonify({
        'success': True,
        'download_url': f'/download/{filename}',
        'filename': filename
    })

@app.route('/download/<filename>')
def download_file(filename):
    """Endpoint to serve downloaded files"""
    filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return "File not found", 404
    
    # Send file for download
    return send_file(
        filepath,
        as_attachment=True,
        download_name=f"video_{filename.split('.')[0]}.mp4"
    )

@app.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'message': 'File too large'}), 413

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)