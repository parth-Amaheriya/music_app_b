import yt_dlp
from pathlib import Path
from typing import List, Dict

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

class YouTubeMusic:
    
    COOKIES_PATH = "cookies/cookies.txt"

    # Print cookie status when class is loaded
    @staticmethod
    def _print_cookie_status():
        cookie_file = Path(YouTubeMusic.COOKIES_PATH)
        if cookie_file.exists():
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                print(f"✅ Cookies loaded successfully | Path: {cookie_file} | Cookies count: {len(lines)}")
            except Exception as e:
                print(f"⚠️ Cookies file exists but could not read it: {e}")
        else:
            print(f"❌ Cookies file NOT found at: {cookie_file}")
            print("   → YouTube may show 'Sign in to confirm you're not a bot' error")

    # Call this once when the module is imported
    _print_cookie_status()

    @staticmethod
    def _get_ydl_base_opts():
        opts = {
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'http_headers': {
                'Referer': 'https://www.youtube.com/',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web', 'web_embedded', 'web_safari'],
                    'player_skip': ['default', 'web'],
                }
            },
            'geo_bypass': True,
            'sleep_interval': 5,
            'max_sleep_interval': 10,
        }

        cookie_file = Path(YouTubeMusic.COOKIES_PATH)
        if cookie_file.exists():
            opts['cookies'] = str(cookie_file)
            print("🍪 yt-dlp is using cookies.txt for this request")
        else:
            print("⚠️ Running WITHOUT cookies - high chance of bot detection")

        return opts

    @staticmethod
    def _get_best_thumbnail(entry: Dict) -> str:
        if not entry:
            return None
            
        thumbnails = entry.get('thumbnails', [])
        if thumbnails:
            best = max(thumbnails, key=lambda x: x.get('width', 0) * x.get('height', 0))
            return best.get('url')
        
        if entry.get('thumbnail'):
            return entry.get('thumbnail')
        
        video_id = entry.get('id')
        return f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if video_id else None

    @staticmethod
    def _get_best_audio_url(entry: Dict) -> str:
        if not entry:
            return None

        formats = entry.get('formats', []) or []
        audio_formats = [f for f in formats if f.get('url') and f.get('acodec') not in (None, 'none')]

        if audio_formats:
            best = max(audio_formats, key=lambda f: (f.get('abr') or 0, f.get('tbr') or 0))
            return best.get('url')

        return entry.get('url')

    # ===================== SEARCH =====================
    @staticmethod
    def search(query: str, limit: int = 10) -> List[Dict]:
        ydl_opts = YouTubeMusic._get_ydl_base_opts()
        ydl_opts.update({
            'extract_flat': True,
            'quiet': True,
        })

        search_url = f"ytsearch{limit}:{query}"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
                results = []
                for entry in info.get('entries', []):
                    if not entry: continue
                    duration = entry.get('duration')
                    duration_str = f"{int(duration//60)}:{int(duration%60):02d}" if duration else "N/A"

                    results.append({
                        "id": entry.get('id'),
                        "title": entry.get('title'),
                        "uploader": entry.get('uploader'),
                        "duration": duration_str,
                        "url": f"https://music.youtube.com/watch?v={entry.get('id')}",
                        "poster_url": YouTubeMusic._get_best_thumbnail(entry),
                    })
                return results
        except Exception as e:
            print(f"Search error: {e}")
            return []

    # ===================== DOWNLOAD =====================
    @staticmethod
    def download_audio(url: str, task_id: str) -> Dict:
        output_template = str(DOWNLOAD_DIR / f"%(title)s_{task_id}.%(ext)s")

        ydl_opts = YouTubeMusic._get_ydl_base_opts()
        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
            }],
            'writethumbnail': True,
            'embedthumbnail': True,
            'addmetadata': True,
            'quiet': False,
        })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_path = Path(ydl.prepare_filename(info)).with_suffix('.opus')

                return {
                    "status": "success",
                    "title": info.get('title'),
                    "filename": final_path.name,
                    "download_url": f"/download/{final_path.name}",
                    "task_id": task_id
                }
        except Exception as e:
            error = str(e)
            if "Sign in to confirm" in error or "bot" in error.lower():
                return {
                    "status": "error",
                    "error": "YouTube blocked the request. Please update cookies.txt"
                }
            return {"status": "error", "error": error}

    # ===================== INFO & RECOMMENDATIONS =====================
    @staticmethod
    def get_info(url: str) -> Dict:
        ydl_opts = YouTubeMusic._get_ydl_base_opts()
        ydl_opts['extract_flat'] = False

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "id": info.get('id'),
                    "title": info.get('title'),
                    "uploader": info.get('uploader'),
                    "duration": info.get('duration'),
                    "view_count": info.get('view_count'),
                    "poster_url": YouTubeMusic._get_best_thumbnail(info),
                    "url": info.get('webpage_url'),
                    "stream_url": YouTubeMusic._get_best_audio_url(info),
                }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_recommendations(url: str, limit: int = 10) -> List[Dict]:
        try:
            video_id = url.split('v=')[-1].split('&')[0]
            playlist_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"

            ydl_opts = YouTubeMusic._get_ydl_base_opts()
            ydl_opts.update({
                'extract_flat': True,
                'playlistend': limit + 15,
            })

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                return [
                    {
                        "title": entry.get('title'),
                        "uploader": entry.get('uploader'),
                        "url": f"https://music.youtube.com/watch?v={entry.get('id')}",
                        "id": entry.get('id'),
                        "poster_url": YouTubeMusic._get_best_thumbnail(entry)
                    }
                    for entry in info.get('entries', [])[:limit] if entry
                ]
        except Exception as e:
            print(f"Recommendations error: {e}")
            return []