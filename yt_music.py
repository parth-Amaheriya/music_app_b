import yt_dlp
from pathlib import Path
from typing import List, Dict

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

class YouTubeMusic:
    
    @staticmethod
    def _get_best_thumbnail(entry: Dict) -> str:
        """Extract best quality poster/thumbnail URL"""
        if not entry:
            return None
            
        # Try thumbnails list first
        thumbnails = entry.get('thumbnails', [])
        if thumbnails:
            best = max(thumbnails, key=lambda x: x.get('width', 0) * x.get('height', 0))
            return best.get('url')
        
        # Fallback to standard thumbnail
        if entry.get('thumbnail'):
            return entry.get('thumbnail')
        
        # Ultimate fallback
        video_id = entry.get('id')
        if video_id:
            return f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        return None

    @staticmethod
    def _get_best_audio_url(entry: Dict) -> str:
        """Extract a direct audio stream URL when yt-dlp exposes one."""
        if not entry:
            return None

        formats = entry.get('formats', []) or []
        audio_formats = [
            format_entry for format_entry in formats
            if format_entry.get('url') and format_entry.get('acodec') not in (None, 'none')
        ]

        if audio_formats:
            best = max(
                audio_formats,
                key=lambda format_entry: (format_entry.get('abr') or 0, format_entry.get('tbr') or 0),
            )
            return best.get('url')

        return entry.get('url')

    @staticmethod
    def search(query: str, limit: int = 10) -> List[Dict]:
        """Search YouTube Music"""
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True,
        }
        search_url = f"ytsearch{limit}:\"{query}\""

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
                if not info or 'entries' not in info:
                    return []

                results = []
                for entry in info['entries']:
                    if not entry:
                        continue
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

    @staticmethod
    def get_info(url: str) -> Dict:
        """Get detailed info"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False
        }
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
    def download_audio(url: str, task_id: str) -> Dict:
        """Download audio"""
        output_template = DOWNLOAD_DIR / f"%(title)s_{task_id}.%(ext)s"

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_template),
            'quiet': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'ios', 'android'],
                }
            },
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '0',
            }],
            'writethumbnail': True,
            'embedthumbnail': True,
            'addmetadata': True,
            'embedmetadata': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                final_path = Path(filename).with_suffix('.opus')

                return {
                    "status": "success",
                    "title": info.get('title'),
                    "filename": final_path.name,
                    "download_url": f"/download/{final_path.name}",
                    "poster_url": YouTubeMusic._get_best_thumbnail(info),
                    "task_id": task_id
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def get_recommendations(url: str, limit: int = 10) -> List[Dict]:
        """Get recommendations"""
        try:
            video_id = url.split('v=')[-1].split('&')[0]
            playlist_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"

            ydl_opts = {
                'extract_flat': True,
                'playlistend': limit + 10,
                'quiet': True,
            }

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