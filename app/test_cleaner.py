import os
import json
from json_cleaner import JSONCleaner
import logging

# Set up logging to console only for testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_single_file(file_path: str):
    """Test JSON cleaning on a single file."""
    cleaner = JSONCleaner(os.path.dirname(file_path))
    
    # Print original JSON
    logger.info("Original JSON content:")
    with open(file_path, 'r', encoding='utf-8') as f:
        original_data = json.load(f)
        print(json.dumps(original_data, indent=2))
    
    # Process the file
    cleaner.process_json_file(file_path)
    
    # Print cleaned JSON
    cleaned_file = file_path.rsplit('.', 2)[0] + '.cleaned.json'
    if os.path.exists(cleaned_file):
        logger.info("\nCleaned JSON content:")
        with open(cleaned_file, 'r', encoding='utf-8') as f:
            cleaned_data = json.load(f)
            print(json.dumps(cleaned_data, indent=2))
    else:
        logger.error("Cleaned file was not created!")

if __name__ == "__main__":
    test_file = r"D:\Documents\Boxing_Legends_Videos_downloads\THE FIGHT with Teddy Atlas\Unknown Playlist\metadata\Cus D'Amato - The Power of Belief - Explained by Teddy Atlas ｜ The Fight Tactics.info.json.info.json"
    test_single_file(test_file) 