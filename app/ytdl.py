import os
import yt_dlp
from collections import OrderedDict
import shelve
import time
import asyncio
import multiprocessing
import logging
import re
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
import uuid
import sqlite3

import yt_dlp.networking.impersonate
from dl_formats import get_format, get_opts, AUDIO_FORMATS
from json_cleaner import JSONCleaner

# Configure logging
log = logging.getLogger('ytdl')
log.setLevel(logging.DEBUG)

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# File handler for detailed debug logs
debug_handler = RotatingFileHandler(
    'logs/debug.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
debug_handler.setFormatter(debug_formatter)
log.addHandler(debug_handler)

# File handler for metadata extraction logs
metadata_handler = RotatingFileHandler(
    'logs/metadata.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
metadata_handler.setLevel(logging.INFO)
metadata_formatter = logging.Formatter(
    '%(asctime)s - %(message)s'
)
metadata_handler.setFormatter(metadata_formatter)
log.addHandler(metadata_handler)

# File handler for errors
error_handler = RotatingFileHandler(
    'logs/error.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s'
)
error_handler.setFormatter(error_formatter)
log.addHandler(error_handler)

class RetryableError(Exception):
    pass

class DownloadQueueNotifier:
    async def added(self, dl):
        raise NotImplementedError

    async def updated(self, dl):
        raise NotImplementedError

    async def completed(self, dl):
        raise NotImplementedError

    async def canceled(self, id):
        raise NotImplementedError

    async def cleared(self, id):
        raise NotImplementedError

class DownloadInfo:
    def __init__(self, id, title, url, quality, format, folder, custom_name_prefix, error):
        # Keep original field order and initialization
        self.id = id
        self.title = title
        self.url = url
        self.quality = quality
        self.format = format 
        self.folder = folder
        self.custom_name_prefix = custom_name_prefix
        self.error = error  # Add error field here
        # Original status fields
        self.msg = self.percent = self.speed = self.eta = None
        self.status = "pending"
        self.size = None
        self.timestamp = time.time_ns()

    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'quality': self.quality,
            'format': self.format,
            'folder': self.folder,
            'custom_name_prefix': self.custom_name_prefix,
            'playlist_strict_mode': self.playlist_strict_mode,
            'playlist_item_limit': self.playlist_item_limit,
            'title': self.title,
            'status': self.status,
            'error': self.error,
            'progress': self.progress,
            'eta': self.eta,
            'speed': self.speed,
            'playlist_count': self.playlist_count,
            'playlist_index': self.playlist_index,
            'filepath': self.filepath,
            'thumbnail': self.thumbnail,
            'description': self.description,
            'info_json': self.info_json,
            'subtitles': self.subtitles,
            'created_time': self.created_time
        }

    @classmethod
    def from_dict(cls, d):
        info = cls(d['id'], d['title'], d['url'], d['quality'], d['format'], d['folder'], d['custom_name_prefix'], d['error'])
        info.id = d.get('id', str(uuid.uuid4()))
        info.title = d.get('title')
        info.status = d.get('status')
        info.error = d.get('error')
        info.progress = d.get('progress')
        info.eta = d.get('eta')
        info.speed = d.get('speed')
        info.playlist_count = d.get('playlist_count')
        info.playlist_index = d.get('playlist_index')
        info.filepath = d.get('filepath')
        info.thumbnail = d.get('thumbnail')
        info.description = d.get('description')
        info.info_json = d.get('info_json')
        info.subtitles = d.get('subtitles')
        info.created_time = d.get('created_time', datetime.now().isoformat())
        info.metadata_status = d.get('metadata_status', {
            'description': {'status': 'pending'},
            'thumbnail': {'status': 'pending'},
            'info_json': {'status': 'pending'},
            'subtitles': {'status': 'pending'},
            'transcript': {'status': 'pending'}
        })
        info.metadata = d.get('metadata', {
            'video': {
                'description': None,
                'duration': None,
                'view_count': None,
                'like_count': None,
                'comment_count': None,
                'upload_date': None
            },
            'channel': {
                'id': None,
                'name': None,
                'subscriber_count': None
            },
            'playlist': {
                'id': None,
                'title': None,
                'index': None
            },
            'transcript': {
                'language': 'en',
                'content': []
            },
            'files': {
                'audio': None,
                'thumbnail': None,
                'description': None,
                'info_json': None,
                'subtitles': []
            }
        })
        return info

class Download:
    manager = None

    def __init__(self, download_dir, temp_dir, output_template, output_template_chapter, quality, format, ytdl_opts, info):
        self.download_dir = download_dir
        self.temp_dir = temp_dir
        self.output_template = output_template
        self.output_template_chapter = output_template_chapter
        self.format = get_format(format, quality)
        self.ytdl_opts = get_opts(format, quality, ytdl_opts)
        self.info = info
        self.canceled = False
        self.tmpfilename = None
        self.status_queue = None
        self.proc = None
        self.loop = None
        self.notifier = None


    def _download(self):
        try:
            def count_videos():
                """Count total videos before starting download"""
                try:
                    with yt_dlp.YoutubeDL({
                        'quiet': True,
                        'extract_flat': True,
                        'no_color': True,
                        'ignoreerrors': True,
                        'noplaylist': self.info.playlist_strict_mode,
                        'playlist_items': '1-1000' if self.info.playlist_item_limit == 0 else f'1-{self.info.playlist_item_limit}'
                    }) as ydl:
                        result = ydl.extract_info(self.info.url, download=False)
                        if result:
                            total = len(result.get('entries', [])) if result.get('entries') else 1
                            self.status_queue.put({
                                'status': 'counting',
                                'total_videos': total,
                                'msg': f'Found {total} videos to download'
                            })
                            return total
                except Exception as e:
                    log.error(f"Error counting videos: {str(e)}")
                    return None

            # Count videos first
            total_videos = count_videos()
            if total_videos:
                self.info.total_videos = total_videos
                self.info.completed_videos = 0

            def update_metadata_status(key, status='error', error_msg=None):
                self.metadata_status[key]['status'] = status
                if error_msg:
                    self.metadata_status[key]['error'] = error_msg
                    log.error(f"Metadata extraction error for {key}: {error_msg}")
                self.status_queue.put({
                    'metadata_status': self.metadata_status,
                    'metadata': self.metadata
                })

            def retry_operation(operation, key=None, max_retries=3):
                retry_count = 0
                last_error = None
                
                while retry_count < max_retries:
                    try:
                        result = operation()
                        if key:
                            log.info(f"Successfully processed {key} on attempt {retry_count + 1}")
                        return result
                    except Exception as e:
                        retry_count += 1
                        last_error = e
                        if key:
                            self.metadata_status[key]['retries'] = retry_count
                            log.warning(f"Retry {retry_count}/{max_retries} for {key}: {str(e)}")
                        time.sleep(self.retry_delay * retry_count)  # Exponential backoff
                
                if key:
                    update_metadata_status(key, 'error', f"Failed after {max_retries} retries: {str(last_error)}")
                raise RetryableError(f"Operation failed after {max_retries} retries: {str(last_error)}")

            def put_status(st):
                if st.get('status') == 'finished':
                    if hasattr(self.info, 'total_videos'):
                        self.info.completed_videos += 1
                        st['completed_videos'] = self.info.completed_videos
                        st['total_videos'] = self.info.total_videos
                        st['msg'] = f'Downloaded {self.info.completed_videos}/{self.info.total_videos} videos'

                if 'info_dict' in st:
                    info = st['info_dict']
                    try:
                        # Track file paths with retry logic
                        if 'filepath' in info:
                            base_path = os.path.dirname(info['filepath'])
                            filename = os.path.basename(info['filepath'])
                            name, ext = os.path.splitext(filename)

                            paths = {
                                'description': os.path.join(base_path, 'descriptions', f'{name}.txt'),
                                'thumbnail': os.path.join(base_path, 'thumbnails', f'{name}.jpg'),
                                'info_json': os.path.join(base_path, 'metadata', f'{name}.info.json'),
                                'audio': info['filepath']
                            }
                            
                            # Create directories if they don't exist
                            for subdir in ['descriptions', 'thumbnails', 'metadata']:
                                dir_path = os.path.join(base_path, subdir)
                                if not os.path.exists(dir_path):
                                    os.makedirs(dir_path)
                            
                            for key, path in paths.items():
                                def check_and_update_file(k=key, p=path):
                                    if os.path.exists(p):
                                        self.metadata['files'][k] = p
                                        update_metadata_status(k, 'completed')
                                        log.info(f"Successfully processed {k} file: {p}")
                                    else:
                                        raise RetryableError(f"File not found: {p}")
                                
                                try:
                                    retry_operation(
                                        check_and_update_file,
                                        key,
                                        max_retries=self.max_retries
                                    )
                                except RetryableError as e:
                                    log.error(f"Failed to process {key}: {str(e)}")

                            # Check for subtitles with retry
                            def process_subtitles():
                                srt_file = os.path.join(base_path, f'{name}.en.srt')
                                if os.path.exists(srt_file):
                                    self.metadata['files']['subtitles'].append(srt_file)
                                    return True
                                raise RetryableError("Subtitle file not found")
                            
                            try:
                                retry_operation(
                                    process_subtitles,
                                    'subtitles',
                                    max_retries=self.max_retries
                                )
                                update_metadata_status('subtitles', 'completed')
                            except RetryableError:
                                update_metadata_status('subtitles', 'error', 'No subtitles found after retries')

                    except Exception as e:
                        log.error(f"Error processing metadata: {str(e)}", exc_info=True)
                        for key in self.metadata_status:
                            update_metadata_status(key, 'error', str(e))

                status_update = {k: v for k, v in st.items() if k in (
                    'tmpfilename',
                    'filename',
                    'status',
                    'msg',
                    'total_bytes',
                    'total_bytes_estimate',
                    'downloaded_bytes',
                    'speed',
                    'eta',
                    'completed_videos',
                    'total_videos'
                )}

                if hasattr(self.info, 'total_videos'):
                    status_update['total_videos'] = self.info.total_videos
                    status_update['completed_videos'] = getattr(self.info, 'completed_videos', 0)

                self.status_queue.put(status_update)

            def process_transcript(d):
                if d['status'] == 'finished' and 'filepath' in d.get('info_dict', {}):
                    filepath = d['info_dict']['filepath']
                    
                    def extract_transcript():
                        base, _ = os.path.splitext(filepath)
                        srt_file = f"{base}.en.srt"
                        
                        if os.path.exists(srt_file):
                            with open(srt_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                segments = parse_srt(content)
                                if segments:
                                    self.metadata_status['transcript']['status'] = 'completed'
                                    self.metadata_status['transcript']['content'] = segments
                                    log.info(f"Successfully extracted transcript: {len(segments)} segments")
                                    return True
                        raise RetryableError("No transcript content found")
                    
                    try:
                        retry_operation(
                            extract_transcript,
                            'transcript',
                            max_retries=self.max_retries
                        )
                        
                        # Write structured metadata with retry
                        def write_metadata():
                            metadata_file = os.path.join(os.path.dirname(filepath), 'metadata.json')
                            with open(metadata_file, 'w', encoding='utf-8') as f:
                                json.dump({
                                    'metadata': self.metadata,
                                    'metadata_status': self.metadata_status
                                }, f, indent=2, ensure_ascii=False)
                            log.info(f"Successfully wrote metadata file: {metadata_file}")
                        
                        retry_operation(
                            write_metadata,
                            'info_json',
                            max_retries=self.max_retries
                        )
                    except RetryableError as e:
                        log.error(f"Failed to process transcript: {str(e)}", exc_info=True)
                        update_metadata_status('transcript', 'error', str(e))

            def parse_srt(content):
                segments = []
                current_segment = {}
                for line in content.split('\n'):
                    line = line.strip()
                    if line.isdigit():  # Segment number
                        if current_segment:
                            segments.append(current_segment)
                        current_segment = {}
                    elif '-->' in line:  # Timestamp
                        start, end = line.split(' --> ')
                        current_segment['start'] = parse_timestamp(start)
                        current_segment['end'] = parse_timestamp(end)
                    elif line:  # Text content
                        if 'text' not in current_segment:
                            current_segment['text'] = line
                        else:
                            current_segment['text'] += ' ' + line
                if current_segment:
                    segments.append(current_segment)
                return segments

            def parse_timestamp(ts):
                h, m, s = ts.replace(',', '.').split(':')
                return float(h) * 3600 + float(m) * 60 + float(s)

            # Prepare download options
            ytdl_opts = {
                'quiet': True,
                'no_color': True,
                'paths': {"home": self.download_dir, "temp": self.temp_dir},
                'outtmpl': { 
                    "default": self.output_template, 
                    "chapter": self.output_template_chapter,
                    "subtitle": "%(channel)s/%(playlist_title|Videos)s/%(title)s.%(ext)s",
                    "description": "%(channel)s/%(playlist_title|Videos)s/descriptions/%(title)s.description",
                    "infojson": "%(channel)s/%(playlist_title|Videos)s/metadata/%(title)s.info.json"
                },
                'format': self.format,
                'socket_timeout': 30,
                'ignore_no_formats_error': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitlesformat': 'vtt',
                'writedescription': True,
                'writeinfojson': True,
                'progress_hooks': [put_status],
                'postprocessor_hooks': [process_transcript],
                'noplaylist': self.info.playlist_strict_mode,
                'playlist_items': '1-1000' if self.info.playlist_item_limit == 0 else f'1-{self.info.playlist_item_limit}'
            }
            
            # Merge with user options, but don't override our critical settings
            for key, value in self.ytdl_opts.items():
                if key not in ['quiet', 'no_color', 'paths', 'outtmpl', 'progress_hooks', 'postprocessor_hooks', 'noplaylist', 'playlist_items']:
                    ytdl_opts[key] = value

            ret = yt_dlp.YoutubeDL(params=ytdl_opts).download([self.info.url])

            # Run JSON cleaner after successful download
            if ret == 0:
                try:
                    cleaner = JSONCleaner(self.download_dir)
                    stats = cleaner.process_all_files()
                    self.status_queue.put({
                        'status': 'cleaning_json',
                        'msg': f"Cleaned {stats['success']} JSON files. Failed: {stats['failed']}"
                    })
                except Exception as e:
                    log.error(f"Error running JSON cleaner: {str(e)}")
                    self.status_queue.put({
                        'status': 'warning',
                        'msg': f"Download successful but JSON cleaning failed: {str(e)}"
                    })

            self.status_queue.put({'status': 'finished' if ret == 0 else 'error'})
        except yt_dlp.utils.YoutubeDLError as exc:
            self.status_queue.put({'status': 'error', 'msg': str(exc)})

    async def start(self, notifier):
        if Download.manager is None:
            Download.manager = multiprocessing.Manager()
        self.status_queue = Download.manager.Queue()
        self.proc = multiprocessing.Process(target=self._download)
        
        log.info(f"Starting download process for {self.info.title} (ID: {self.info.id})")
        self.proc.start()
        
        self.loop = asyncio.get_running_loop()
        self.notifier = notifier
        self.info.status = 'preparing'
        await self.notifier.updated(self.info)
        asyncio.create_task(self.update_status())
        return await self.loop.run_in_executor(None, self.proc.join)

    def cancel(self):
        if self.running():
            log.info(f"Canceling download for {self.info.title} (ID: {self.info.id})")
            self.proc.kill()
        self.canceled = True

    def close(self):
        if self.started():
            log.info(f"Closing download process for {self.info.title} (ID: {self.info.id})")
            self.proc.close()
            self.status_queue.put(None)

    def running(self):
        try:
            return self.proc is not None and self.proc.is_alive()
        except ValueError:
            return False

    def started(self):
        return self.proc is not None

    async def update_status(self):
        while True:
            status = await self.loop.run_in_executor(None, self.status_queue.get)
            if status is None:
                return
                
            try:
                self.tmpfilename = status.get('tmpfilename')
                if 'filename' in status:
                    fileName = status.get('filename')
                    self.info.filename = os.path.relpath(fileName, self.download_dir)
                    self.info.size = os.path.getsize(fileName) if os.path.exists(fileName) else None
                    log.info(f"File saved: {self.info.filename} (Size: {self.info.size})")

                # Update metadata progress
                if 'metadata_status' in status:
                    old_status = self.info.metadata_status.copy() if hasattr(self.info, 'metadata_status') else {}
                    self.info.metadata_status = status['metadata_status']
                    
                    # Log metadata status changes
                    for key, new_status in self.info.metadata_status.items():
                        old = old_status.get(key, {}).get('status')
                        new = new_status.get('status')
                        if old != new:
                            if new == 'completed':
                                log.info(f"Metadata extraction completed for {key}")
                            elif new == 'error':
                                log.error(f"Metadata extraction failed for {key}: {new_status.get('error')}")

                # Update download status
                old_status = self.info.status
                self.info.status = status['status']
                if old_status != self.info.status:
                    log.info(f"Download status changed from {old_status} to {self.info.status}")
                
                self.info.msg = status.get('msg')
                if self.info.msg:
                    log.info(f"Download message: {self.info.msg}")

                # Update progress
                if 'downloaded_bytes' in status:
                    total = status.get('total_bytes') or status.get('total_bytes_estimate')
                    if total:
                        self.info.percent = status['downloaded_bytes'] / total * 100
                        log.debug(f"Download progress: {self.info.percent:.1f}%")

                self.info.speed = status.get('speed')
                self.info.eta = status.get('eta')
                
                # Log completion or errors
                if self.info.status == 'finished':
                    log.info(f"Download completed successfully for {self.info.title}")
                    # Log metadata extraction summary
                    if hasattr(self.info, 'metadata_status'):
                        completed = sum(1 for s in self.info.metadata_status.values() if s.get('status') == 'completed')
                        total = len(self.info.metadata_status)
                        log.info(f"Metadata extraction summary: {completed}/{total} components completed")
                elif self.info.status == 'error':
                    log.error(f"Download failed for {self.info.title}: {self.info.msg}")
                
                await self.notifier.updated(self.info)
                
            except Exception as e:
                log.error(f"Error updating status: {str(e)}", exc_info=True)
                await self.notifier.updated(self.info)

class PersistentQueue:
    def __init__(self, path):
        self.path = path
        self.dict = OrderedDict()
        # Create parent directories if needed
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Connect to SQLite database
        self.conn = sqlite3.connect(f'file:{path}?mode=rwc', uri=True)
        self._init_db()
        self.load()

    def _init_db(self):
        """Initialize the SQLite database schema"""
        self.conn.execute('''CREATE TABLE IF NOT EXISTS queue_items 
                            (id TEXT PRIMARY KEY, 
                             data BLOB,
                             timestamp INTEGER)''')
        self.conn.commit()

    def load(self):
        """Load items from SQLite database into memory"""
        try:
            cursor = self.conn.execute(
                'SELECT id, data FROM queue_items ORDER BY timestamp ASC'
            )
            self.dict.clear()
            for key, value in cursor:
                try:
                    # Deserialize the JSON data
                    data = json.loads(value)
                    if isinstance(data, dict):
                        # Convert dict to DownloadInfo if needed
                        data = DownloadInfo.from_dict(data)
                    self.dict[key] = data
                except Exception as e:
                    log.error(f"Error deserializing item {key}: {str(e)}")
        except Exception as e:
            log.error(f"Error loading queue from {self.path}: {str(e)}")
            self.dict = OrderedDict()  # Reset to empty on error

    def exists(self, key):
        """Check if key exists in queue"""
        return key in self.dict

    def get(self, key):
        """Get item by key"""
        return self.dict[key]

    def items(self):
        """Get all items in queue"""
        return self.dict.items()

    def put(self, value):
        """Add item to queue"""
        if hasattr(value, 'info'):
            key = value.info.url
            self.dict[key] = value
            try:
                # Serialize the data
                data = json.dumps(value.info.to_dict() if hasattr(value.info, 'to_dict') else value.info.__dict__)
                # Update or insert the item
                self.conn.execute(
                    '''INSERT OR REPLACE INTO queue_items (id, data, timestamp) 
                       VALUES (?, ?, ?)''',
                    (key, data, int(time.time() * 1000))
                )
                self.conn.commit()
            except Exception as e:
                log.error(f"Error saving to queue {self.path}: {str(e)}")
        else:
            log.error(f"Invalid value type for queue: {type(value)}")

    def delete(self, key):
        """Remove item from queue"""
        if key in self.dict:
            del self.dict[key]
            try:
                self.conn.execute('DELETE FROM queue_items WHERE id = ?', (key,))
                self.conn.commit()
            except Exception as e:
                log.error(f"Error deleting from queue {self.path}: {str(e)}")

    def next(self):
        """Get next item in queue"""
        try:
            return next(iter(self.dict.items()))
        except StopIteration:
            return None, None

    def empty(self):
        """Check if queue is empty"""
        return not bool(self.dict)

    def close(self):
        """Close database connection"""
        try:
            self.conn.close()
        except Exception as e:
            log.error(f"Error closing queue database {self.path}: {str(e)}")

    def __del__(self):
        """Destructor to ensure database connection is closed"""
        self.close()

class DownloadQueue:
    def __init__(self, config, notifier):
        self.config = config
        self.notifier = notifier
        self.event = asyncio.Event()
        
        # Initialize all three queues
        self.queue = PersistentQueue(os.path.join(config.STATE_DIR, 'queue'))
        self.done = PersistentQueue(os.path.join(config.STATE_DIR, 'completed'))
        self.pending = PersistentQueue(os.path.join(config.STATE_DIR, 'pending'))
        self.done.load()

    async def initialize(self):
        """Initialize the download queue and start background tasks"""
        # Start background tasks
        asyncio.create_task(self.__download())
        await self.__import_queue()

    async def __import_queue(self):
        try:
            for k, v in self.queue.saved_items():
                if isinstance(v, dict):
                    # Convert dict to DownloadInfo if needed
                    v = DownloadInfo.from_dict(v)
                elif isinstance(v, DownloadInfo):
                    # Use existing DownloadInfo object
                    pass
                else:
                    log.error(f"Invalid queue item type: {type(v)}")
                    continue
                
                # Add to queue with default values for missing attributes
                await self.add(
                    url=v.url,
                    quality=getattr(v, 'quality', None),
                    format=getattr(v, 'format', None),
                    folder=getattr(v, 'folder', None),
                    custom_name_prefix=getattr(v, 'custom_name_prefix', None),
                    playlist_strict_mode=getattr(v, 'playlist_strict_mode', False),
                    playlist_item_limit=getattr(v, 'playlist_item_limit', None),
                    auto_start=False  # Send to pending queue
                )
        except Exception as e:
            log.error(f"Error importing queue: {str(e)}", exc_info=True)

    def save_queue(self):
        try:
            queue_file = os.path.join(self.config.STATE_DIR, '.metube', 'queue.json')
            with open(queue_file, 'w') as f:
                json.dump(self.queue, f)
        except Exception as e:
            log.error(f"Error saving queue: {str(e)}")

    def __extract_info(self, url, playlist_strict_mode):
        # Check if input is a channel ID and convert to URL if needed
        if re.match(r'^UC[\w-]{22}$', url):
            url = f'https://www.youtube.com/channel/{url}'
        elif re.match(r'^@[\w.-]+$', url):
            url = f'https://www.youtube.com/{url}'
            
        return yt_dlp.YoutubeDL(params={
            'quiet': True,
            'no_color': True,
            'extract_flat': True,
            'ignoreerrors': True,
            'playlist_items': '1-1000',
            'noplaylist': playlist_strict_mode,
            'paths': {"home": self.config.DOWNLOAD_DIR, "temp": self.config.TEMP_DIR},
            **({'impersonate': yt_dlp.networking.impersonate.ImpersonateTarget.from_str(self.config.YTDL_OPTIONS['impersonate'])} if 'impersonate' in self.config.YTDL_OPTIONS else {}),
            **self.config.YTDL_OPTIONS,
        }).extract_info(url, download=False)

    def __calc_download_path(self, quality, format, folder):
        """Calculates download path from quality, format and folder attributes.

        Returns:
            Tuple dldirectory, error_message both of which might be None (but not at the same time)
        """
        # Keep consistent with frontend
        base_directory = self.config.DOWNLOAD_DIR if (quality != 'audio' and format not in AUDIO_FORMATS) else self.config.AUDIO_DOWNLOAD_DIR
        if folder:
            if not self.config.CUSTOM_DIRS:
                return None, {'status': 'error', 'msg': f'A folder for the download was specified but CUSTOM_DIRS is not true in the configuration.'}
            dldirectory = os.path.realpath(os.path.join(base_directory, folder))
            real_base_directory = os.path.realpath(base_directory)
            if not dldirectory.startswith(real_base_directory):
                return None, {'status': 'error', 'msg': f'Folder "{folder}" must resolve inside the base download directory "{real_base_directory}"'}
            if not os.path.isdir(dldirectory):
                if not self.config.CREATE_CUSTOM_DIRS:
                    return None, {'status': 'error', 'msg': f'Folder "{folder}" for download does not exist inside base directory "{real_base_directory}", and CREATE_CUSTOM_DIRS is not true in the configuration.'}
                os.makedirs(dldirectory, exist_ok=True)
        else:
            dldirectory = base_directory
        return dldirectory, None

    async def __add_entry(self, entry, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already):
        if not entry:
            return {'status': 'error', 'msg': "Invalid/empty data was given."}

        error = None
        if "live_status" in entry and "release_timestamp" in entry and entry.get("live_status") == "is_upcoming":
            dt_ts = datetime.fromtimestamp(entry.get("release_timestamp")).strftime('%Y-%m-%d %H:%M:%S %z')
            error = f"Live stream is scheduled to start at {dt_ts}"
        else:
            if "msg" in entry:
                error = entry["msg"]

        etype = entry.get('_type') or 'video'

        if etype.startswith('url'):
            log.debug('Processing as an url')
            return await self.add(entry['url'], quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already)
        elif etype == 'playlist':
            log.debug('Processing as a playlist')
            entries = entry['entries']
            total_entries = len(entries)
            log.info(f'playlist/channel detected with {total_entries} entries')
            playlist_index_digits = len(str(total_entries))
            results = []
            
            # Extract playlist/channel metadata
            playlist_data = {
                'id': entry.get('id'),
                'title': entry.get('title'),
                'uploader': entry.get('uploader'),
                'uploader_id': entry.get('uploader_id'),
                'playlist': entry.get('id'),
                'playlist_title': entry.get('title'),
                'playlist_uploader': entry.get('uploader'),
                'playlist_uploader_id': entry.get('uploader_id')
            }
            
            log.info(f'Channel/Playlist metadata: {playlist_data}')
            
            # Process all entries in batches
            BATCH_SIZE = 50  # Process 50 videos at a time
            BATCH_PAUSE = 10  # 10 second pause between batches
            
            for batch_start in range(0, total_entries, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total_entries)
                batch = entries[batch_start:batch_end]
                
                log.info(f'Processing batch {batch_start//BATCH_SIZE + 1} of {(total_entries + BATCH_SIZE - 1)//BATCH_SIZE} ({batch_start+1}-{batch_end} of {total_entries} videos)')
                
                for index, etr in enumerate(batch, start=batch_start + 1):
                    etr["_type"] = "video"
                    etr.update(playlist_data)
                    etr["playlist_index"] = '{{0:0{0:d}d}}'.format(playlist_index_digits).format(index)
                    results.append(await self.__add_entry(etr, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already))
                
                # If this isn't the last batch, pause before continuing
                if batch_end < total_entries:
                    log.info(f'Pausing for {BATCH_PAUSE} seconds before next batch...')
                    await asyncio.sleep(BATCH_PAUSE)
            
            if any(res['status'] == 'error' for res in results):
                return {'status': 'error', 'msg': ', '.join(res['msg'] for res in results if res['status'] == 'error' and 'msg' in res)}
            return {'status': 'ok'}
        elif etype == 'video' or etype.startswith('url') and 'id' in entry and 'title' in entry:
            log.debug('Processing as a video')
            if not self.queue.exists(entry['id']):
                # Create DownloadInfo with all required parameters
                dl = DownloadInfo(
                    id=entry['id'],
                    title=entry.get('title') or entry['id'],
                    url=entry.get('webpage_url') or entry['url'],
                    quality=quality,
                    format=format,
                    folder=folder,
                    custom_name_prefix=custom_name_prefix,
                    error=error,
                    playlist_strict_mode=playlist_strict_mode,
                    playlist_item_limit=playlist_item_limit
                )
                # Set additional attributes
                dl.status = 'pending'
                
                # Set playlist-related attributes if available
                if 'playlist' in entry:
                    dl.playlist_count = entry.get('playlist_count')
                    dl.playlist_index = entry.get('playlist_index')
                
                dldirectory, error_message = self.__calc_download_path(quality, format, folder)
                if error_message is not None:
                    return error_message
                output = self.config.OUTPUT_TEMPLATE if len(custom_name_prefix) == 0 else f'{custom_name_prefix}.{self.config.OUTPUT_TEMPLATE}'
                output_chapter = self.config.OUTPUT_TEMPLATE_CHAPTER
                if 'playlist' in entry and entry['playlist'] is not None:
                    if len(self.config.OUTPUT_TEMPLATE_PLAYLIST):
                        output = self.config.OUTPUT_TEMPLATE_PLAYLIST

                    for property, value in entry.items():
                        if property.startswith("playlist"):
                            output = output.replace(f"%({property})s", str(value))

                ytdl_options = dict(self.config.YTDL_OPTIONS)

                if playlist_item_limit > 0:
                    log.info(f'playlist limit is set. Processing only first {playlist_item_limit} entries')
                    ytdl_options['playlistend'] = playlist_item_limit

                if auto_start is True:
                    self.queue.put(Download(dldirectory, self.config.TEMP_DIR, output, output_chapter, quality, format, ytdl_options, dl))
                    self.event.set()
                else:
                    self.pending.put(Download(dldirectory, self.config.TEMP_DIR, output, output_chapter, quality, format, ytdl_options, dl))
                await self.notifier.added(dl)
            return {'status': 'ok'}
        return {'status': 'error', 'msg': f'Unsupported resource "{etype}"'}

    async def add(self, url, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start=True, already=None):
        log.info(f'adding {url}: {quality=} {format=} {already=} {folder=} {custom_name_prefix=} {playlist_strict_mode=} {playlist_item_limit=}')
        already = set() if already is None else already
        if url in already:
            log.info('recursion detected, skipping')
            return {'status': 'ok'}
        else:
            already.add(url)
        try:
            entry = await asyncio.get_running_loop().run_in_executor(None, self.__extract_info, url, playlist_strict_mode)
        except yt_dlp.utils.YoutubeDLError as exc:
            return {'status': 'error', 'msg': str(exc)}
        return await self.__add_entry(entry, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already)

    async def start_pending(self, ids):
        for id in ids:
            if not self.pending.exists(id):
                log.warn(f'requested start for non-existent download {id}')
                continue
            dl = self.pending.get(id)
            self.queue.put(dl)
            self.pending.delete(id)
            self.event.set()
        return {'status': 'ok'}

    async def cancel(self, ids):
        for id in ids:
            if not self.queue.exists(id):
                log.warn(f'requested cancel for non-existent download {id}')
                continue
            if self.queue.get(id).started():
                self.queue.get(id).cancel()
            else:
                self.queue.delete(id)
                await self.notifier.canceled(id)
        return {'status': 'ok'}

    async def clear(self, ids):
        for id in ids:
            if not self.queue.exists(id):
                log.warn(f'requested delete for non-existent download {id}')
                continue
            if self.config.DELETE_FILE_ON_TRASHCAN:
                dl = self.queue.get(id)
                try:
                    dldirectory, _ = self.__calc_download_path(dl.info.quality, dl.info.format, dl.info.folder)
                    os.remove(os.path.join(dldirectory, dl.info.filename))
                except Exception as e:
                    log.warn(f'deleting file for download {id} failed with error message {e!r}')
            self.queue.delete(id)
            await self.notifier.cleared(id)
        return {'status': 'ok'}

    def get(self):
        return (
            list((k, v.info) for k, v in self.queue.items()) + 
            list((k, v.info) for k, v in self.pending.items()),
            list((k, v.info) for k, v in self.done.items())
        )

    async def __download(self):
        while True:
            while self.queue.empty():
                log.info('waiting for item to download')
                await self.event.wait()
                self.event.clear()
            id, entry = self.queue.next()
            log.info(f'downloading {entry.info.title}')
            await entry.start(self.notifier)
            if entry.info.status != 'finished':
                if entry.tmpfilename and os.path.isfile(entry.tmpfilename):
                    try:
                        os.remove(entry.tmpfilename)
                    except:
                        pass
                entry.info.status = 'error'
            entry.close()
            if self.queue.exists(id):
                self.queue.delete(id)
                if entry.canceled:
                    await self.notifier.canceled(id)
                else:
                    self.done.put(entry)
                    await self.notifier.completed(entry.info)

def get_playlist_videos(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'force_generic_extractor': False
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(url, download=False)
            if 'entries' in result:
                # No limit on number of videos
                return [
                    {'url': entry['url'], 'title': entry['title']}
                    for entry in result['entries']
                    if entry is not None
                ]
            else:
                return [{'url': result['webpage_url'], 'title': result['title']}]
        except Exception as e:
            logger.error(f"Error extracting playlist info: {str(e)}")
            return []
