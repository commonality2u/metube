import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
import glob

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/json_cleaner.log', 'a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class JSONCleaner:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        
    def find_json_files(self) -> List[str]:
        """Find all .info.json files in the directory tree."""
        pattern = os.path.join(self.base_dir, '**', '*.info.json')
        return glob.glob(pattern, recursive=True)
        
    def clean_json_data(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Clean and structure the JSON data."""
        try:
            cleaned_data = {
                "video_info": {
                    "title": data.get("title", ""),
                    "description": data.get("description", ""),
                    "duration": data.get("duration_string", ""),
                    "upload_date": data.get("upload_date", ""),
                    "view_count": data.get("view_count", 0),
                    "like_count": data.get("like_count", 0),
                    "comment_count": data.get("comment_count", 0)
                },
                "channel_info": {
                    "name": data.get("channel", ""),
                    "id": data.get("channel_id", ""),
                    "subscriber_count": data.get("channel_follower_count", 0),
                    "url": data.get("channel_url", "")
                },
                "playlist_info": {
                    "title": data.get("playlist_title", ""),
                    "id": data.get("playlist_id", ""),
                    "index": data.get("playlist_index", ""),
                    "uploader": data.get("playlist_uploader", "")
                },
                "technical_info": {
                    "format": data.get("format", ""),
                    "ext": data.get("ext", ""),
                    "filesize": data.get("filesize", 0),
                    "audio_channels": data.get("audio_channels", 0)
                },
                "metadata": {
                    "processed_date": datetime.now().isoformat(),
                    "original_url": data.get("original_url", ""),
                    "webpage_url": data.get("webpage_url", ""),
                    "extractor": data.get("extractor", "")
                }
            }
            return cleaned_data
        except Exception as e:
            logger.error(f"Error cleaning JSON data: {str(e)}")
            return None

    def process_json_file(self, file_path: str) -> bool:
        """Process a single JSON file."""
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Read the original JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Clean the data
            cleaned_data = self.clean_json_data(data)
            if not cleaned_data:
                return False
                
            # Create the new filename
            base_path = os.path.splitext(file_path)[0]
            new_file_path = f"{base_path}.cleaned.json"
            
            # Write the cleaned data
            with open(new_file_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Created cleaned file: {new_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            return False
            
    def process_all_files(self) -> Dict[str, int]:
        """Process all JSON files in the directory tree."""
        stats = {
            "total": 0,
            "success": 0,
            "failed": 0
        }
        
        json_files = self.find_json_files()
        stats["total"] = len(json_files)
        
        for file_path in json_files:
            if self.process_json_file(file_path):
                stats["success"] += 1
            else:
                stats["failed"] += 1
                
        logger.info(f"Processing complete. Total: {stats['total']}, "
                   f"Successful: {stats['success']}, Failed: {stats['failed']}")
        return stats

if __name__ == "__main__":
    base_dir = r"D:\Documents\Boxing_Legends_Videos_downloads"
    cleaner = JSONCleaner(base_dir)
    cleaner.process_all_files() 