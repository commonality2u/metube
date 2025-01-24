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
    def __init__(self, url, quality='best', format='mp4', folder=None, custom_name_prefix=None, playlist_strict_mode=False, playlist_item_limit=0):
        self.url = url
        self.quality = quality
        self.format = format
        self.folder = folder
        self.custom_name_prefix = custom_name_prefix
        self.playlist_strict_mode = playlist_strict_mode
        self.playlist_item_limit = playlist_item_limit
        self.id = str(uuid.uuid4())
        self.title = None
        self.filename = None
        self.size = None
        self.status = None
        self.msg = None
        self.percent = 0
        self.speed = None
        self.eta = None
        self.checked = False
        self.deleting = False
        self.metadata_status = {
            'description': {'status': 'pending'},
            'thumbnail': {'status': 'pending'},
            'info_json': {'status': 'pending'},
            'subtitles': {'status': 'pending'},
            'transcript': {'status': 'pending'}
        }
        self.metadata = {
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
        }
        self.created_time = datetime.now().isoformat()

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
        info = cls(d['url'], d.get('quality'), d.get('format'), d.get('folder'), 
                  d.get('custom_name_prefix'), d.get('playlist_strict_mode', False), 
                  d.get('playlist_item_limit', 0))
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
        self.retry_delay = 1  # Base delay for retries in seconds
        self.max_retries = 3  # Maximum number of retries for operations
        self._started = False

    def started(self):
        """Check if download has started"""
        return self._started

    async def start(self, notifier):
        """Start the download process using asyncio threads"""
        self.notifier = notifier
        self.loop = asyncio.get_running_loop()
        self.status_queue = asyncio.Queue()  # Use asyncio queue
        self._started = True
        
        # Run the download in a thread
        try:
            await self.loop.run_in_executor(None, self._download)
            
            while True:
                try:
                    status = await asyncio.wait_for(self.status_queue.get(), timeout=1.0)
                    if status.get('status') == 'error':
                        self.info.status = 'error'
                        self.info.msg = status.get('msg', 'Download failed')
                        break
                    elif status.get('status') == 'finished':
                        self.info.status = 'finished'
                        self.info.msg = status.get('msg', 'Download completed')
                        break
                    else:
                        self.info.status = status.get('status')
                        self.info.msg = status.get('msg')
                        self.info.size = status.get('total_bytes') or status.get('total_bytes_estimate')
                        self.info.percent = (status.get('downloaded_bytes', 0) / self.info.size * 100) if self.info.size else 0
                        self.info.speed = status.get('speed')
                        self.info.eta = status.get('eta')
                        self.info.metadata_status = status.get('metadata_status', self.info.metadata_status)
                        self.info.metadata = status.get('metadata', self.info.metadata)
                        if 'tmpfilename' in status:
                            self.tmpfilename = status['tmpfilename']
                        await self.notifier.updated(self.info)
                except asyncio.TimeoutError:
                    # Check if download is still running
                    continue
                except Exception as e:
                    log.error(f'Error in download loop: {str(e)}', exc_info=True)
                    self.info.status = 'error'
                    self.info.msg = str(e)
                    break
        except Exception as e:
            log.error(f'Error starting download: {str(e)}', exc_info=True)
            self.info.status = 'error'
            self.info.msg = str(e)

    def _download(self):
        try:
            def put_status(st):
                if not hasattr(self, 'status_queue') or not self.status_queue:
                    return
                
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.status_queue.put(st),
                        self.loop
                    )
                except Exception as e:
                    log.error(f"Error putting status: {str(e)}")

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

class PersistentQueue:
    def __init__(self, path, **kwargs):
        pdir = os.path.dirname(path)
        if not os.path.isdir(pdir):
            os.makedirs(pdir)
        self.path = path + '.json'
        self.dict = OrderedDict()
        self.load()

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if isinstance(v, dict):
                            v = DownloadInfo.from_dict(v)
                        self.dict[k] = v
        except Exception as e:
            log.error(f"Error loading queue from {self.path}: {str(e)}")
            self.dict = OrderedDict()

    def exists(self, key):
        return key in self.dict

    def get(self, key):
        return self.dict[key]

    def items(self):
        return self.dict.items()

    def saved_items(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r') as f:
                    data = json.load(f)
                    return [(k, v if isinstance(v, DownloadInfo) else DownloadInfo.from_dict(v)) 
                            for k, v in data.items()]
        except Exception as e:
            log.error(f"Error reading saved items from {self.path}: {str(e)}")
            return []

    def put(self, value):
        try:
            if hasattr(value, 'info'):
                key = value.info.url
                self.dict[key] = value
                try:
                    with open(self.path, 'w') as f:
                        data = {}
                        for k, v in self.dict.items():
                            if hasattr(v, 'info'):
                                data[k] = v.info.__dict__ if hasattr(v.info, '__dict__') else v.info
                            else:
                                data[k] = v.__dict__ if hasattr(v, '__dict__') else v
                        json.dump(data, f, indent=2, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o))
                except Exception as e:
                    log.error(f"Error saving to queue {self.path}: {str(e)}")
            else:
                log.error(f"Invalid value type for queue: {type(value)}")
        except Exception as e:
            log.error(f"Error in put operation: {str(e)}", exc_info=True)

    def delete(self, key):
        if key in self.dict:
            del self.dict[key]
            try:
                with open(self.path, 'w') as f:
                    data = {}
                    for k, v in self.dict.items():
                        if hasattr(v, 'info'):
                            data[k] = v.info.__dict__ if hasattr(v.info, '__dict__') else v.info
                        else:
                            data[k] = v.__dict__ if hasattr(v, '__dict__') else v
                    json.dump(data, f, indent=2, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o))
            except Exception as e:
                log.error(f"Error deleting from queue {self.path}: {str(e)}")

    def next(self):
        try:
            return next(iter(self.dict.items()))
        except StopIteration:
            return None, None

    def empty(self):
        return not bool(self.dict)

class DownloadQueue:
    def __init__(self, config, notifier):
        self.config = config
        self.notifier = notifier
        self.event = asyncio.Event()
        
        # Ensure state directory exists
        os.makedirs(self.config.STATE_DIR, exist_ok=True)
        
        # Initialize queue databases properly with more robust error handling
        dbs = ['queue', 'completed', 'pending']
        for db in dbs:
            db_path = os.path.join(self.config.STATE_DIR, db)
            try:
                # Initialize with a simple JSON file instead of shelve
                if not os.path.exists(db_path + '.json'):
                    with open(db_path + '.json', 'w') as f:
                        json.dump({}, f)
            except Exception as e:
                log.error(f"Error initializing database {db_path}: {str(e)}")
                
        self.queue = PersistentQueue(os.path.join(self.config.STATE_DIR, 'queue'))
        self.done = PersistentQueue(os.path.join(self.config.STATE_DIR, 'completed'))
        self.pending = PersistentQueue(os.path.join(self.config.STATE_DIR, 'pending'))
        
        # Import existing queue items and start background tasks
        asyncio.create_task(self.__import_queue())
        asyncio.create_task(self.__download())

    async def __import_queue(self):
        try:
            saved_items = self.queue.saved_items()
            # Clear existing in-memory entries (DownloadInfo)
            self.queue.dict.clear()
            for k, v in saved_items:
                # Directly reconstruct Download object from persisted data
                if isinstance(v, dict):
                    v = DownloadInfo.from_dict(v)
                
                if isinstance(v, DownloadInfo):
                    # Create Download with existing DownloadInfo
                    dldirectory, _ = self.__calc_download_path(v.quality, v.format, v.folder)
                    
                    # Enhanced type validation with error handling
                    try:
                        playlist_item_limit = int(v.playlist_item_limit or 0)
                        playlist_item_limit = max(0, min(playlist_item_limit, 1000))
                    except (TypeError, ValueError):
                        playlist_item_limit = 0
                        log.warning(f"Invalid playlist_item_limit value: {v.playlist_item_limit}")
                    
                    dl = Download(
                        dldirectory,
                        self.config.TEMP_DIR,
                        self.config.OUTPUT_TEMPLATE,
                        self.config.OUTPUT_TEMPLATE_CHAPTER,
                        v.quality,
                        v.format,
                        dict(self.config.YTDL_OPTIONS),
                        v
                    )
                    dl.info.playlist_item_limit = playlist_item_limit
                    self.queue.put(dl)
                    log.debug(f"Restored download queue item: {v.id} with limit {playlist_item_limit}")
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
            BATCH_SIZE = 100  # Increased from 50 to 100
            
            for batch_start in range(0, total_entries, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total_entries)
                batch = entries[batch_start:batch_end]
                
                log.info(f'Processing batch {batch_start//BATCH_SIZE + 1} of {(total_entries + BATCH_SIZE - 1)//BATCH_SIZE} ({batch_start+1}-{batch_end} of {total_entries} videos)')
                
                batch_results = []
                for index, etr in enumerate(batch, start=batch_start + 1):
                    etr["_type"] = "video"
                    etr.update(playlist_data)
                    etr["playlist_index"] = '{{0:0{0:d}d}}'.format(playlist_index_digits).format(index)
                    result = await self.__add_entry(etr, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already)
                    batch_results.append(result)
                    
                    # Trigger event after each successful video addition
                    if result.get('status') == 'ok' and auto_start:
                        self.event.set()
                        
                results.extend(batch_results)
            
            if any(res['status'] == 'error' for res in results):
                return {'status': 'error', 'msg': ', '.join(res['msg'] for res in results if res['status'] == 'error' and 'msg' in res)}
            return {'status': 'ok'}
        elif etype == 'video' or etype.startswith('url') and 'id' in entry and 'title' in entry:
            log.debug('Processing as a video')
            if not self.queue.exists(entry['id']):
                # Create DownloadInfo with all required parameters
                dl = DownloadInfo(
                    url=entry.get('webpage_url') or entry['url'],
                    quality=quality,
                    format=format,
                    folder=folder,
                    custom_name_prefix=custom_name_prefix,
                    playlist_strict_mode=playlist_strict_mode,
                    playlist_item_limit=playlist_item_limit
                )
                # Set additional attributes
                dl.id = entry['id']
                dl.title = entry.get('title') or entry['id']
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

                # Convert to int and handle None case
                playlist_item_limit = int(playlist_item_limit) if playlist_item_limit else 0
                # Safely handle None/type conversions
                try:
                    playlist_item_limit = int(playlist_item_limit) if playlist_item_limit else 0
                except (ValueError, TypeError):
                    playlist_item_limit = 0
                    
                if playlist_item_limit > 0:
                    log.info(f'playlist limit set to {playlist_item_limit}')
                    ytdl_options['playlistend'] = min(playlist_item_limit, 1000)  # Add safety cap

                # Create the download object
                download = Download(dldirectory, self.config.TEMP_DIR, output, output_chapter, quality, format, ytdl_options, dl)
                self.queue.put(download)
                
                # Always set the event when auto_start is True to trigger the download
                if auto_start is True:
                    self.event.set()
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
            if not self.queue.exists(id):
                log.warn(f'requested start for non-existent download {id}')
                continue
            dl = self.queue.get(id)
            self.queue.put(dl)
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
        return(list((k, v.info) for k, v in self.queue.items()),
               list((k, v.info) for k, v in self.done.items()))

    async def __download(self):
        while True:
            try:
                while self.queue.empty():
                    log.info('waiting for item to download')
                    await self.event.wait()
                    self.event.clear()
                
                id, download = self.queue.next()
                if not id or not download:
                    log.warning('Got empty queue item, continuing...')
                    continue
                    
                log.info(f'Starting download for item {id}')
                
                try:
                    # Ensure download directory exists and is writable
                    dldirectory, _ = self.__calc_download_path(
                        download.info.quality,
                        download.info.format,
                        download.info.folder
                    )
                    if not os.path.exists(dldirectory):
                        os.makedirs(dldirectory, exist_ok=True)
                    
                    # Start the download with proper error handling
                    await download.start(self.notifier)
                    
                    # Handle download completion
                    if download.info.status == 'finished':
                        if self.queue.exists(id):
                            self.queue.delete(id)
                            self.done.put(download)
                            await self.notifier.completed(download.info)
                            log.info(f'Successfully completed download for {id}')
                    else:
                        # Handle failed download
                        if download.tmpfilename and os.path.isfile(download.tmpfilename):
                            try:
                                os.remove(download.tmpfilename)
                            except Exception as e:
                                log.error(f'Error removing temporary file: {str(e)}')
                        
                        download.info.status = 'error'
                        if self.queue.exists(id):
                            self.queue.delete(id)
                            await self.notifier.completed(download.info)
                            log.error(f'Download failed for {id}: {download.info.msg}')
                    
                    # Clean up
                    download.close()
                    
                except Exception as e:
                    log.error(f'Error processing download {id}: {str(e)}', exc_info=True)
                    download.info.status = 'error'
                    download.info.msg = str(e)
                    if self.queue.exists(id):
                        self.queue.delete(id)
                        await self.notifier.completed(download.info)
                    
                # Trigger the event for the next item if queue is not empty
                if not self.queue.empty():
                    self.event.set()
                    
            except Exception as e:
                log.error(f'Critical error in download loop: {str(e)}', exc_info=True)
                # Wait a bit before retrying to prevent tight error loops
                await asyncio.sleep(1)
