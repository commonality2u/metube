import asyncio
import logging
from ytdl import DownloadQueue, DownloadQueueNotifier

# Configure logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('test_async')

class TestConfig:
    def __init__(self):
        self.STATE_DIR = './test_state'
        self.DOWNLOAD_DIR = './test_downloads'
        self.TEMP_DIR = './test_temp'
        self.YTDL_OPTIONS = {}

class TestNotifier(DownloadQueueNotifier):
    async def added(self, dl):
        log.info(f"Download added: {dl.title if hasattr(dl, 'title') else 'Unknown'}")

    async def updated(self, dl):
        log.info(f"Download updated: {dl.title if hasattr(dl, 'title') else 'Unknown'}")

    async def completed(self, dl):
        log.info(f"Download completed: {dl.title if hasattr(dl, 'title') else 'Unknown'}")

    async def canceled(self, id):
        log.info(f"Download canceled: {id}")

    async def cleared(self, id):
        log.info(f"Download cleared: {id}")

async def main():
    # Initialize event loop
    loop = asyncio.get_running_loop()
    log.info("Event loop initialized")

    # Create config and queue
    config = TestConfig()
    dqueue = DownloadQueue(config, TestNotifier())
    
    # Initialize queue
    await dqueue.initialize()
    log.info("Download queue initialized")

    # Keep the script running for a few seconds
    try:
        await asyncio.sleep(5)
        log.info("Test completed successfully")
    except Exception as e:
        log.error(f"Error during test: {str(e)}")
    finally:
        # Clean up
        for task in asyncio.all_tasks(loop):
            if task is not asyncio.current_task():
                task.cancel()

if __name__ == '__main__':
    asyncio.run(main()) 