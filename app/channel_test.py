import yt_dlp
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/channel_test.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def get_channel_info(channel_url):
    """
    Extract all video information from a YouTube channel
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'ignoreerrors': True,
        'dump_single_json': True,
        'playlist_items': '1-1000',  # Try to get up to 1000 videos to test the limit
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Starting extraction from: {channel_url}")
            result = ydl.extract_info(channel_url, download=False)
            
            if not result:
                logger.error("No results found")
                return
            
            videos = []
            if 'entries' in result:
                # Process each video entry
                for idx, entry in enumerate(result['entries'], 1):
                    if entry:
                        video_info = {
                            'index': idx,
                            'title': entry.get('title', 'N/A'),
                            'upload_date': entry.get('upload_date', 'N/A'),
                            'view_count': entry.get('view_count', 0),
                            'duration': entry.get('duration', 0),
                            'video_id': entry.get('id', 'N/A')
                        }
                        videos.append(video_info)
                        logger.info(f"Processed video {idx}: {video_info['title']}")
            
            # Save results to JSON file
            output = {
                'channel_name': result.get('channel', 'N/A'),
                'channel_id': result.get('channel_id', 'N/A'),
                'total_videos': len(videos),
                'extraction_date': datetime.now().isoformat(),
                'videos': videos
            }
            
            with open('channel_info.json', 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Total videos found: {len(videos)}")
            logger.info(f"Results saved to channel_info.json")
            
            return output
            
    except Exception as e:
        logger.error(f"Error during extraction: {str(e)}", exc_info=True)
        return None

if __name__ == "__main__":
    channel_url = "https://www.youtube.com/@GregIsenberg/videos"
    get_channel_info(channel_url) 