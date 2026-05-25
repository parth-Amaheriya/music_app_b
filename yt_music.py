import yt_dlp
from pathlib import Path
from typing import List, Dict

DOWNLOAD_DIR = Path("downloads")

class YouTubeMusic:
    
    @staticmethod
    def search(query: str, limit: int = 10) -> List[Dict]:
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True,
        }
        search_url = f"ytsearch{limit}:\"{query}\""

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
                    "thumbnail": entry.get('thumbnail')
                })
            return results

    @staticmethod
    def get_info(url: str) -> Dict:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "id": info.get('id'),
                "title": info.get('title'),
                "uploader": info.get('uploader'),
                "duration": info.get('duration'),
                "view_count": info.get('view_count'),
                "thumbnail": info.get('thumbnail'),
                "url": info.get('webpage_url')
            }

    @staticmethod
    def download_audio(url: str, task_id: str) -> Dict:
        output_template = DOWNLOAD_DIR / f"%(title)s_{task_id}.%(ext)s"

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_template),
            'quiet': False,
            'extractor_args': {'youtube': {'player_client': ['web', 'ios', 'android']}},
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

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            final_path = Path(filename).with_suffix('.opus')

            return {
                "status": "success",
                "title": info.get('title'),
                "filename": final_path.name,
                "download_url": f"/download/{final_path.name}",
                "task_id": task_id
            }

    @staticmethod
    def get_recommendations(url: str, limit: int = 10) -> List[Dict]:
        try:
            video_id = url.split('v=')[-1].split('&')[0]
            playlist_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"

            ydl_opts = {'extract_flat': True, 'playlistend': limit + 10, 'quiet': True}

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                return [
                    {
                        "title": entry.get('title'),
                        "uploader": entry.get('uploader'),
                        "url": f"https://music.youtube.com/watch?v={entry.get('id')}",
                        "id": entry.get('id')
                    }
                    for entry in info.get('entries', [])[:limit] if entry
                ]
        except:
            return []