import yt_dlp
from pathlib import Path
from typing import List, Dict
import os 
from dotenv import load_dotenv
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = ROOT_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

class YouTubeMusic:
    
    COOKIES_PATH = ROOT_DIR / "cookies.txt"

    @staticmethod
    def _get_cookiefile_path() -> Path | None:
        override_path = os.getenv("YTDLP_COOKIEFILE")
        cookie_file = Path(override_path).expanduser() if override_path else YouTubeMusic.COOKIES_PATH
        return cookie_file if cookie_file.exists() else None

    @staticmethod
    def _print_cookie_status():
        try:
            cookie_file = YouTubeMusic._get_cookiefile_path() or YouTubeMusic.COOKIES_PATH
            if cookie_file.exists():
                content = cookie_file.read_text(encoding='utf-8')
                cookie_count = len([line for line in content.splitlines() 
                                  if line.strip() and not line.startswith('#')])
                print(f"✅ SUCCESS: Cookies loaded | {cookie_count} cookies found")
            else:
                print(f"❌ WARNING: cookies.txt NOT FOUND at {cookie_file.absolute()}")
                print("   → App will continue without cookies (YouTube will likely block)")
        except Exception as e:
            print(f"⚠️ ERROR during cookie check: {e}")

    @staticmethod
    def _get_proxy():
        """Get proxy from environment variable"""
        proxy = os.getenv("PROXY_URL")
        print(f"🔍 Checking for proxy... PROXY_URL={proxy}")
        if proxy:
            print(f"🌐 Using Proxy: {proxy}")
            return proxy
        return None
    
    @staticmethod
    def _get_ydl_base_opts():
        opts = {
            'ignoreconfig': True,
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'http_headers': {
                'Referer': 'https://music.youtube.com/',
                'Origin': 'https://music.youtube.com',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web', 'web_music', 'web_creator', 'web_embedded'],
                    'po_token': True,
                    'web_po_token': True,
                    'fetch_pot': 'auto',
                }
            },
            'geo_bypass': True,
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
        }

        # Proxy (if using)
        proxy = YouTubeMusic._get_proxy()
        if proxy:
            opts['proxy'] = proxy
            print(f"🌐 Using Proxy: {proxy}")

        # Cookies
        cookie_file = YouTubeMusic._get_cookiefile_path()
        if cookie_file:
            opts['cookiefile'] = str(cookie_file)
            print("🍪 Using cookies.txt")
        else:
            print("⚠️ No cookies.txt - high risk of blocking")

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
    def _codec_priority(codec: str | None) -> int:
        if not codec or codec == 'none':
            return 0

        normalized = codec.lower()

        if 'opus' in normalized:
            return 400

        if normalized.startswith('mp4a') or 'aac' in normalized:
            return 300

        if 'flac' in normalized:
            return 250

        if 'vorbis' in normalized or 'ogg' in normalized:
            return 200

        return 100

    @staticmethod
    def _format_audio_stream(fmt: Dict) -> Dict:
        bitrate = int(fmt.get('abr') or fmt.get('tbr') or 0)
        return {
            "url": fmt.get('url'),
            "format_id": fmt.get('format_id'),
            "codec": fmt.get('acodec'),
            "bitrate": bitrate,
            "ext": fmt.get('ext'),
            "format_note": fmt.get('format_note'),
            "sample_rate": fmt.get('asr'),
            "filesize": fmt.get('filesize'),
            "filesize_approx": fmt.get('filesize_approx'),
            "language": fmt.get('language'),
        }

    @staticmethod
    def _select_audio_formats(entry: Dict, limit: int = 6) -> List[Dict]:
        if not isinstance(entry, dict):
            return []

        seen_urls = set()
        audio_formats = []

        formats = entry.get('formats') or []
        if not isinstance(formats, list):
            formats = []

        for fmt in formats:
            if not isinstance(fmt, dict):
                continue

            url = fmt.get('url')
            if not url or url in seen_urls:
                continue

            if fmt.get('vcodec') not in (None, 'none'):
                continue

            codec = fmt.get('acodec')
            if codec in (None, 'none'):
                continue

            seen_urls.add(url)
            audio_formats.append(YouTubeMusic._format_audio_stream(fmt))

        audio_formats.sort(
            key=lambda fmt: (
                YouTubeMusic._codec_priority(fmt.get('codec')),
                int(fmt.get('bitrate') or 0),
                int(fmt.get('filesize') or fmt.get('filesize_approx') or 0),
            ),
            reverse=True,
        )

        return audio_formats[:limit]
    
    @staticmethod
    def _get_best_audio_url(entry: Dict) -> str:
        audio_formats = YouTubeMusic._select_audio_formats(entry, limit=1)

        if audio_formats:
            return audio_formats[0].get('url')

        return entry.get('url') if entry else None

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

        base_opts = YouTubeMusic._get_ydl_base_opts()
        base_opts.update({
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

        format_attempts = [
            'bestaudio/best',
            'bestaudio',
            'best',
            None,
        ]

        try:
            last_error = None
            info = None

            for format_selector in format_attempts:
                ydl_opts = dict(base_opts)
                if format_selector:
                    ydl_opts['format'] = format_selector

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        final_path = Path(ydl.prepare_filename(info)).with_suffix('.opus')
                        break
                except Exception as exc:
                    last_error = exc
                    if 'Requested format is not available' not in str(exc):
                        raise

            if info is None:
                raise last_error

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
        ydl_opts.update({
            'extract_flat': False,
            'quiet': True,
            'no_warnings': True,
        })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Critical Fix: Handle case when yt-dlp returns bool instead of dict
                if not isinstance(info, dict):
                    return {"error": f"Failed to extract info. Got unexpected type: {type(info)}"}

                audio_formats = YouTubeMusic._select_audio_formats(info, limit=8)

                best_format = audio_formats[0] if audio_formats else None
                best_audio_url = best_format.get('url') if best_format else None

                return {
                    "id": info.get('id'),
                    "title": info.get('title'),
                    "uploader": info.get('uploader'),
                    "duration": info.get('duration'),
                    "view_count": info.get('view_count'),
                    "poster_url": YouTubeMusic._get_best_thumbnail(info),
                    "url": info.get('webpage_url'),
                    "best_audio_url": best_audio_url,
                    "best_codec": best_format.get('codec') if best_format else None,
                    "best_bitrate": best_format.get('bitrate') if best_format else 0,
                    "best_ext": best_format.get('ext') if best_format else None,
                    "audio_formats": audio_formats,
                    "stream_url": best_audio_url,
                }
        except Exception as e:
            print(f"get_info error for {url}: {str(e)}")
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

YouTubeMusic._print_cookie_status()        