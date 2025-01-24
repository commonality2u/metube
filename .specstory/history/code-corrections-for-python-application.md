## SpecStory

## Code Corrections for Python Application (1/23/2025, 11:20:17 PM)

_**User**_

please make these changes. 
1. **Duplicate `init_app` Function**: The file has two implementations of `init_app`:

```94:100:app/main.py
async def init_app(app):
    """Initialize the application"""
    global dqueue
    dqueue = DownloadQueue(config, Notifier())
    await dqueue.initialize()
    log.info("Application initialized successfully")
    return app
```

and

```191:197:app/main.py
async def init_app(app):
    """Initialize the application"""
    global dqueue
    dqueue = DownloadQueue(config, Notifier())
    await dqueue.initialize()
    log.info("Application initialized successfully")
    return app
```


2. **Incorrect Route Addition Order**: Routes are being added twice:

```324:329:app/main.py
try:
    app.add_routes(routes)
except ValueError as e:
    if 'ui/dist/metube' in str(e):
        raise RuntimeError('Could not find the frontend UI static assets. Please run `node_modules/.bin/ng build` inside the ui folder') from e
    raise e
```

and again at

```410:412:app/main.py
    app.add_routes(routes)
    app.on_response_prepare.append(on_prepare)
    app.on_startup.append(init_app)
```


3. **Event Loop Management**: The application is trying to manage event loops in multiple places, which can cause conflicts.

Here's the corrected version of the main startup section:

```python
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log.info(f"Listening on {config.HOST}:{config.PORT}")

    # Add routes and middleware only once
    app.add_routes(routes)
    app.on_response_prepare.append(on_prepare)
    app.on_startup.append(init_app)  # Single initialization point

    # SSL configuration
    ssl_context = None
    if config.HTTPS:
        if not config.CERTFILE or not config.KEYFILE:
            log.error('HTTPS is enabled but CERTFILE or KEYFILE is not set')
            sys.exit(1)
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(config.CERTFILE, config.KEYFILE)

    # Port reuse configuration
    reuse_port = supports_reuse_port()
    if not reuse_port:
        log.warning('Port reuse is not supported on this platform')

    # Start the application
    web.run_app(
        app, 
        host=config.HOST, 
        port=int(config.PORT), 
        ssl_context=ssl_context, 
        reuse_port=reuse_port
    )
```

The key changes are:
1. Remove the duplicate `init_app` function (keep only one)
2. Move route addition and middleware setup before `web.run_app`
3. Let aiohttp manage the event loop through `web.run_app`




---

_**Assistant**_

I'll help you make these changes. Let me analyze the file and make the necessary edits.

First, I'll edit the file to remove the duplicate `init_app` function and fix the route addition order.

---

_**Assistant**_

```
// ... existing code ...
class Config:
    _DEFAULTS = {
// ... existing code ...

async def init_app(app):
    """Initialize the application"""
    global dqueue
    dqueue = DownloadQueue(config, Notifier())
    await dqueue.initialize()
    log.info("Application initialized successfully")
    return app
    
config = Config()

class ObjectSerializer(json.JSONEncoder):
// ... existing code ...
routes.static(config.URL_PREFIX + 'download/', config.DOWNLOAD_DIR, show_index=config.DOWNLOAD_DIRS_INDEXABLE)
routes.static(config.URL_PREFIX + 'audio_download/', config.AUDIO_DOWNLOAD_DIR, show_index=config.DOWNLOAD_DIRS_INDEXABLE)
routes.static(config.URL_PREFIX, os.path.join(config.BASE_DIR, 'ui/dist/metube'))

# https://github.com/aio-libs/aiohttp/pull/4615 waiting for release
# @routes.options(config.URL_PREFIX + 'add')
async def add_cors(request):
    return web.Response(text=serializer.encode({"status": "ok"}))

app.router.add_route('OPTIONS', config.URL_PREFIX + 'add', add_cors)

async def on_prepare(request, response):
    if 'Origin' in request.headers:
        response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

app.on_response_prepare.append(on_prepare)

def supports_reuse_port():
// ... existing code ...
@routes.get(config.URL_PREFIX + 'metadata')
async def get_all_metadata(request):
    metadata = {
        'completed': [],
        'active': []
    }
    
    # Get metadata for completed downloads
    for id, dl in dqueue.done.items():
        if hasattr(dl.info, 'metadata') and hasattr(dl.info, 'metadata_status'):
            metadata['completed'].append({
                'id': id,
                'metadata': dl.info.metadata,
                'metadata_status': dl.info.metadata_status
            })
    
    # Get metadata for active downloads
    for id, dl in dqueue.queue.items():
        if hasattr(dl.info, 'metadata') and hasattr(dl.info, 'metadata_status'):
            metadata['active'].append({
                'id': id,
                'metadata': dl.info.metadata,
                'metadata_status': dl.info.metadata_status
            })
    
    return web.Response(text=serializer.encode(metadata))

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log.info(f"Listening on {config.HOST}:{config.PORT}")

    # Add routes and middleware only once
    app.add_routes(routes)
    app.on_response_prepare.append(on_prepare)
    app.on_startup.append(init_app)  # Single initialization point

    # SSL configuration
    ssl_context = None
    if config.HTTPS:
        if not config.CERTFILE or not config.KEYFILE:
            log.error('HTTPS is enabled but CERTFILE or KEYFILE is not set')
            sys.exit(1)
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(config.CERTFILE, config.KEYFILE)

    # Port reuse configuration
    reuse_port = supports_reuse_port()
    if not reuse_port:
        log.warning('Port reuse is not supported on this platform')

    # Start the application
    web.run_app(
        app,
        host=config.HOST,
        port=int(config.PORT),
        ssl_context=ssl_context,
        reuse_port=reuse_port
    )
```

---

_**Assistant**_



I'll make another edit to ensure all the changes are properly applied:

---

_**Assistant**_

```
// ... existing code ...
routes.static(config.URL_PREFIX + 'download/', config.DOWNLOAD_DIR, show_index=config.DOWNLOAD_DIRS_INDEXABLE)
routes.static(config.URL_PREFIX + 'audio_download/', config.AUDIO_DOWNLOAD_DIR, show_index=config.DOWNLOAD_DIRS_INDEXABLE)
routes.static(config.URL_PREFIX, os.path.join(config.BASE_DIR, 'ui/dist/metube'))

# https://github.com/aio-libs/aiohttp/pull/4615 waiting for release
# @routes.options(config.URL_PREFIX + 'add')
async def add_cors(request):
    return web.Response(text=serializer.encode({"status": "ok"}))

app.router.add_route('OPTIONS', config.URL_PREFIX + 'add', add_cors)

async def on_prepare(request, response):
    if 'Origin' in request.headers:
        response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

// ... existing code ...
```

---

_**Assistant**_



Let me try one more time with a more specific edit:

---

_**Assistant**_

```
// ... existing code ...
if config.URL_PREFIX != '/':
    @routes.get('/')
    def index_redirect_root(request):
        return web.HTTPFound(config.URL_PREFIX)

    @routes.get(config.URL_PREFIX[:-1])
    def index_redirect_dir(request):
        return web.HTTPFound(config.URL_PREFIX)

routes.static(config.URL_PREFIX + 'download/', config.DOWNLOAD_DIR, show_index=config.DOWNLOAD_DIRS_INDEXABLE)
routes.static(config.URL_PREFIX + 'audio_download/', config.AUDIO_DOWNLOAD_DIR, show_index=config.DOWNLOAD_DIRS_INDEXABLE)
routes.static(config.URL_PREFIX, os.path.join(config.BASE_DIR, 'ui/dist/metube'))

# https://github.com/aio-libs/aiohttp/pull/4615 waiting for release
# @routes.options(config.URL_PREFIX + 'add')
async def add_cors(request):
    return web.Response(text=serializer.encode({"status": "ok"}))

app.router.add_route('OPTIONS', config.URL_PREFIX + 'add', add_cors)

async def on_prepare(request, response):
    if 'Origin' in request.headers:
        response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

def supports_reuse_port():
// ... existing code ...
```

---

_**Assistant**_



I see that the changes are not being applied as expected. Let me try a different approach with a more targeted edit:

---

_**Assistant**_

```
// ... existing code ...
@routes.get(config.URL_PREFIX + 'metadata')
async def get_all_metadata(request):
    metadata = {
        'completed': [],
        'active': []
    }
    
    # Get metadata for completed downloads
    for id, dl in dqueue.done.items():
        if hasattr(dl.info, 'metadata') and hasattr(dl.info, 'metadata_status'):
            metadata['completed'].append({
                'id': id,
                'metadata': dl.info.metadata,
                'metadata_status': dl.info.metadata_status
            })
    
    # Get metadata for active downloads
    for id, dl in dqueue.queue.items():
        if hasattr(dl.info, 'metadata') and hasattr(dl.info, 'metadata_status'):
            metadata['active'].append({
                'id': id,
                'metadata': dl.info.metadata,
                'metadata_status': dl.info.metadata_status
            })
    
    return web.Response(text=serializer.encode(metadata))

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log.info(f"Listening on {config.HOST}:{config.PORT}")

    # Add routes and middleware only once
    app.add_routes(routes)
    app.on_response_prepare.append(on_prepare)
    app.on_startup.append(init_app)  # Single initialization point

    # SSL configuration
    ssl_context = None
    if config.HTTPS:
        if not config.CERTFILE or not config.KEYFILE:
            log.error('HTTPS is enabled but CERTFILE or KEYFILE is not set')
            sys.exit(1)
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(config.CERTFILE, config.KEYFILE)

    # Port reuse configuration
    reuse_port = supports_reuse_port()
    if not reuse_port:
        log.warning('Port reuse is not supported on this platform')

    # Start the application
    web.run_app(
        app,
        host=config.HOST,
        port=int(config.PORT),
        ssl_context=ssl_context,
        reuse_port=reuse_port
    )
```

---

_**Assistant**_



I apologize for the difficulty in applying the changes. Let me try one final time with a complete file replacement:

---

_**Assistant**_

```
#!/usr/bin/env python3
# pylint: disable=no-member,method-hidden

import os
import sys
from aiohttp import web
import ssl
import socket
import socketio
import logging
import json
import pathlib
import asyncio
from json_cleaner import JSONCleaner

from ytdl import DownloadQueueNotifier, DownloadQueue

# Configure logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('main')

class Config:
    _DEFAULTS = {
        'DOWNLOAD_DIR': '.',
        'AUDIO_DOWNLOAD_DIR': '%%DOWNLOAD_DIR',
        'TEMP_DIR': '%%DOWNLOAD_DIR',
        'DOWNLOAD_DIRS_INDEXABLE': 'false',
        'CUSTOM_DIRS': 'true',
        'CREATE_CUSTOM_DIRS': 'true',
        'DELETE_FILE_ON_TRASHCAN': 'false',
        'STATE_DIR': '.',
        'URL_PREFIX': '',
        'PUBLIC_HOST_URL': 'download/',
        'PUBLIC_HOST_AUDIO_URL': 'audio_download/',
        'OUTPUT_TEMPLATE': '%(channel)s/%(title)s.%(ext)s',
        'OUTPUT_TEMPLATE_CHAPTER': '%(channel)s/%(playlist_title|Videos)s/chapters/%(title)s - %(section_number)s %(section_title)s.%(ext)s',
        'OUTPUT_TEMPLATE_PLAYLIST': '%(channel)s/%(playlist_title|Videos)s/%(title)s.%(ext)s',
        'OUTPUT_TEMPLATE_SUBTITLES': '%(channel)s/%(playlist_title|Videos)s/%(title)s.%(ext)s',
        'OUTPUT_TEMPLATE_DESCRIPTION': '%(channel)s/%(playlist_title|Videos)s/descriptions/%(title)s.%(ext)s',
        'OUTPUT_TEMPLATE_METADATA': '%(channel)s/%(playlist_title|Videos)s/metadata/%(title)s.%(ext)s',
        'DEFAULT_OPTION_PLAYLIST_STRICT_MODE': 'false',
        'DEFAULT_OPTION_PLAYLIST_ITEM_LIMIT': '0',
        'YTDL_OPTIONS': '{}',
        'YTDL_OPTIONS_FILE': '',
        'ROBOTS_TXT': '',
        'HOST': '0.0.0.0',
        'PORT': '8081',
        'HTTPS': 'false',
        'CERTFILE': '',
        'KEYFILE': '',
        'BASE_DIR': '',
        'DEFAULT_THEME': 'auto'
    }

    _BOOLEAN = ('DOWNLOAD_DIRS_INDEXABLE', 'CUSTOM_DIRS', 'CREATE_CUSTOM_DIRS', 'DELETE_FILE_ON_TRASHCAN', 'DEFAULT_OPTION_PLAYLIST_STRICT_MODE', 'HTTPS')

    def __init__(self):
        for k, v in self._DEFAULTS.items():
            setattr(self, k, os.environ[k] if k in os.environ else v)

        for k, v in self.__dict__.items():
            if v.startswith('%%'):
                setattr(self, k, getattr(self, v[2:]))
            if k in self._BOOLEAN:
                if v not in ('true', 'false', 'True', 'False', 'on', 'off', '1', '0'):
                    log.error(f'Environment variable "{k}" is set to a non-boolean value "{v}"')
                    sys.exit(1)
                setattr(self, k, v in ('true', 'True', 'on', '1'))

        if not self.URL_PREFIX.endswith('/'):
            self.URL_PREFIX += '/'

        try:
            self.YTDL_OPTIONS = json.loads(self.YTDL_OPTIONS)
            assert isinstance(self.YTDL_OPTIONS, dict)
        except (json.decoder.JSONDecodeError, AssertionError):
            log.error('YTDL_OPTIONS is invalid')
            sys.exit(1)

        if self.YTDL_OPTIONS_FILE:
            log.info(f'Loading yt-dlp custom options from "{self.YTDL_OPTIONS_FILE}"')
            if not os.path.exists(self.YTDL_OPTIONS_FILE):
                log.error(f'File "{self.YTDL_OPTIONS_FILE}" not found')
                sys.exit(1)
            try:
                with open(self.YTDL_OPTIONS_FILE) as json_data:
                    opts = json.load(json_data)
                assert isinstance(opts, dict)
            except (json.decoder.JSONDecodeError, AssertionError):
                log.error('YTDL_OPTIONS_FILE contents is invalid')
                sys.exit(1)
            self.YTDL_OPTIONS.update(opts)

async def init_app(app):
    """Initialize the application"""
    global dqueue
    dqueue = DownloadQueue(config, Notifier())
    await dqueue.initialize()
    log.info("Application initialized successfully")
    return app
    
config = Config()

class ObjectSerializer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, object):
            return obj.__dict__
        else:
            return json.JSONEncoder.default(self, obj)

serializer = ObjectSerializer()
app = web.Application()
sio = socketio.AsyncServer(cors_allowed_origins='*')
sio.attach(app, socketio_path=config.URL_PREFIX + 'socket.io')
routes = web.RouteTableDef()

class Notifier(DownloadQueueNotifier):
    def __init__(self):
        self.json_cleaner = JSONCleaner(r"D:\Documents\Boxing_Legends_Videos_downloads")
        
    async def added(self, dl):
        data = ObjectSerializer().default(dl)
        if hasattr(dl, 'metadata_status'):
            data['metadata_status'] = dl.metadata_status
        await sio.emit('added', data)

    async def updated(self, dl):
        data = ObjectSerializer().default(dl)
        if hasattr(dl, 'metadata_status'):
            data['metadata_status'] = dl.metadata_status
        if hasattr(dl, 'metadata'):
            data['metadata'] = dl.metadata
        
        # Include any error messages
        if dl.error:
            data['error'] = dl.error
        
        # Check for metadata-specific errors
        if hasattr(dl, 'metadata_status'):
            errors = {}
            for key, status in dl.metadata_status.items():
                if status.get('status') == 'error' and 'error' in status:
                    errors[key] = status['error']
            if errors:
                data['metadata_errors'] = errors
        
        await sio.emit('updated', data)

    async def completed(self, dl):
        data = ObjectSerializer().default(dl)
        if hasattr(dl, 'metadata_status'):
            data['metadata_status'] = dl.metadata_status
        if hasattr(dl, 'metadata'):
            data['metadata'] = dl.metadata
            
        # Include metadata extraction summary
        if hasattr(dl, 'metadata_status'):
            summary = {
                'total': len(dl.metadata_status),
                'completed': sum(1 for s in dl.metadata_status.values() if s.get('status') == 'completed'),
                'failed': sum(1 for s in dl.metadata_status.values() if s.get('status') == 'error'),
                'errors': {k: v.get('error') for k, v in dl.metadata_status.items() if v.get('status') == 'error' and 'error' in v}
            }
            data['metadata_summary'] = summary
            
        await sio.emit('completed', data)
        
        # Trigger JSON cleaning after download completes
        try:
            log.info(f"Starting JSON cleaning for completed download: {dl.title}")
            asyncio.create_task(self._clean_json_files())
        except Exception as e:
            log.error(f"Error during JSON cleaning: {str(e)}", exc_info=True)

    async def _clean_json_files(self):
        """Run the JSON cleaner asynchronously"""
        try:
            # Run the JSON cleaner in a thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            stats = await loop.run_in_executor(None, self.json_cleaner.process_all_files)
            log.info(f"JSON cleaning completed. Stats: {stats}")
        except Exception as e:
            log.error(f"Error in JSON cleaning task: {str(e)}", exc_info=True)

    async def canceled(self, id):
        await sio.emit('canceled', {'id': id})

    async def cleared(self, id):
        await sio.emit('cleared', {'id': id})

@routes.post(config.URL_PREFIX + 'add')
async def add(request):
    post = await request.json()
    url = post.get('url')
    quality = post.get('quality')
    if not url or not quality:
        raise web.HTTPBadRequest()
    format = post.get('format')
    folder = post.get('folder')
    custom_name_prefix = post.get('custom_name_prefix')
    playlist_strict_mode = post.get('playlist_strict_mode')
    playlist_item_limit = post.get('playlist_item_limit')
    auto_start = post.get('auto_start')

    if custom_name_prefix is None:
        custom_name_prefix = ''
    if auto_start is None:
        auto_start = True
    if playlist_strict_mode is None:
        playlist_strict_mode = config.DEFAULT_OPTION_PLAYLIST_STRICT_MODE
    if playlist_item_limit is None:
        playlist_item_limit = config.DEFAULT_OPTION_PLAYLIST_ITEM_LIMIT

    playlist_item_limit = int(playlist_item_limit)

    status = await dqueue.add(url, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start)
    return web.Response(text=serializer.encode(status))

@routes.post(config.URL_PREFIX + 'delete')
async def delete(request):
    post = await request.json()
    ids = post.get('ids')
    where = post.get('where')
    if not ids or where not in ['queue', 'done']:
        raise web.HTTPBadRequest()
    status = await (dqueue.cancel(ids) if where == 'queue' else dqueue.clear(ids))
    return web.Response(text=serializer.encode(status))

@routes.post(config.URL_PREFIX + 'start')
async def start(request):
    post = await request.json()
    ids = post.get('ids')
    status = await dqueue.start_pending(ids)
    return web.Response(text=serializer.encode(status))

@routes.get(config.URL_PREFIX + 'history')
async def history(request):
    history = { 'done': [], 'queue': [], 'pending': []}

    for _ ,v in dqueue.queue.saved_items():
        history['queue'].append(v)
    for _ ,v in dqueue.done.saved_items():
        history['done'].append(v)
    for _ ,v in dqueue.pending.saved_items():
        history['pending'].append(v)

    return web.Response(text=serializer.encode(history))

@sio.event
async def connect(sid, environ):
    await sio.emit('all', serializer.encode(dqueue.get()), to=sid)
    await sio.emit('configuration', serializer.encode(config), to=sid)
    if config.CUSTOM_DIRS:
        await sio.emit('custom_dirs', serializer.encode(get_custom_dirs()), to=sid)

def get_custom_dirs():
    def recursive_dirs(base):
        path = pathlib.Path(base)

        # Converts PosixPath object to string, and remove base/ prefix
        def convert(p):
            s = str(p)
            if s.startswith(base):
                s = s[len(base):]

            if s.startswith('/'):
                s = s[1:]

            return s

        # Recursively lists all subdirectories of DOWNLOAD_DIR
        dirs = list(filter(None, map(convert, path.glob('**'))))

        return dirs

    download_dir = recursive_dirs(config.DOWNLOAD_DIR)

    audio_download_dir = download_dir
    if config.DOWNLOAD_DIR != config.AUDIO_DOWNLOAD_DIR:
        audio_download_dir = recursive_dirs(config.AUDIO_DOWNLOAD_DIR)

    return {
        "download_dir": download_dir,
        "audio_download_dir": audio_download_dir
    }

@routes.get(config.URL_PREFIX)
def index(request):
    response = web.FileResponse(os.path.join(config.BASE_DIR, 'ui/dist/metube/index.html'))
    if 'metube_theme' not in request.cookies:
        response.set_cookie('metube_theme', config.DEFAULT_THEME)
    return response

@routes.get(config.URL_PREFIX + 'robots.txt')
def robots(request):
    if config.ROBOTS_TXT:
        response = web.FileResponse(os.path.join(config.BASE_DIR, config.ROBOTS_TXT))
    else:
        response = web.Response(
            text="User-agent: *\nDisallow: /download/\nDisallow: /audio_download/\n"
        )
    return response

if config.URL_PREFIX != '/':
    @routes.get('/')
    def index_redirect_root(request):
        return web.HTTPFound(config.URL_PREFIX)

    @routes.get(config.URL_PREFIX[:-1])
    def index_redirect_dir(request):
        return web.HTTPFound(config.URL_PREFIX)

routes.static(config.URL_PREFIX + 'download/', config.DOWNLOAD_DIR, show_index=config.DOWNLOAD_DIRS_INDEXABLE)
routes.static(config.URL_PREFIX + 'audio_download/', config.AUDIO_DOWNLOAD_DIR, show_index=config.DOWNLOAD_DIRS_INDEXABLE)
routes.static(config.URL_PREFIX, os.path.join(config.BASE_DIR, 'ui/dist/metube'))

# https://github.com/aio-libs/aiohttp/pull/4615 waiting for release
# @routes.options(config.URL_PREFIX + 'add')
async def add_cors(request):
    return web.Response(text=serializer.encode({"status": "ok"}))

app.router.add_route('OPTIONS', config.URL_PREFIX + 'add', add_cors)

async def on_prepare(request, response):
    if 'Origin' in request.headers:
        response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

def supports_reuse_port():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.close()
        return True
    except (AttributeError, OSError):
        return False

@routes.get(config.URL_PREFIX + 'metadata/{id}')
async def get_metadata(request):
    id = request.match_info['id']
    
    # Check completed downloads first
    if dqueue.done.exists(id):
        dl = dqueue.done.get(id)
        if hasattr(dl.info, 'metadata') and hasattr(dl.info, 'metadata_status'):
            return web.Response(text=serializer.encode({
                'metadata': dl.info.metadata,
                'metadata_status': dl.info.metadata_status
            }))
    
    # Check active downloads
    if dqueue.queue.exists(id):
        dl = dqueue.queue.get(id)
        if hasattr(dl.info, 'metadata') and hasattr(dl.info, 'metadata_status'):
            return web.Response(text=serializer.encode({
                'metadata': dl.info.metadata,
                'metadata_status': dl.info.metadata_status
            }))
    
    raise web.HTTPNotFound(text=serializer.encode({
        'status': 'error',
        'message': f'No metadata found for id: {id}'
    }))

@routes.get(config.URL_PREFIX + 'metadata')
async def get_all_metadata(request):
    metadata = {
        'completed': [],
        'active': []
    }
    
    # Get metadata for completed downloads
    for id, dl in dqueue.done.items():
        if hasattr(dl.info, 'metadata') and hasattr(dl.info, 'metadata_status'):
            metadata['completed'].append({
                'id': id,
                'metadata': dl.info.metadata,
                'metadata_status': dl.info.metadata_status
            })
    
    # Get metadata for active downloads
    for id, dl in dqueue.queue.items():
        if hasattr(dl.info, 'metadata') and hasattr(dl.info, 'metadata_status'):
            metadata['active'].append({
                'id': id,
                'metadata': dl.info.metadata,
                'metadata_status': dl.info.metadata_status
            })
    
    return web.Response(text=serializer.encode(metadata))

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log.info(f"Listening on {config.HOST}:{config.PORT}")

    # Add routes and middleware only once
    app.add_routes(routes)
    app.on_response_prepare.append(on_prepare)
    app.on_startup.append(init_app)  # Single initialization point

    # SSL configuration
    ssl_context = None
    if config.HTTPS:
        if not config.CERTFILE or not config.KEYFILE:
            log.error('HTTPS is enabled but CERTFILE or KEYFILE is not set')
            sys.exit(1)
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(config.CERTFILE, config.KEYFILE)

    # Port reuse configuration
    reuse_port = supports_reuse_port()
    if not reuse_port:
        log.warning('Port reuse is not supported on this platform')

    # Start the application
    web.run_app(
        app,
        host=config.HOST,
        port=int(config.PORT),
        ssl_context=ssl_context,
        reuse_port=reuse_port
    )
```

---

_**Assistant**_



I've made all the requested changes to the file:

1. Removed the duplicate `init_app` function
2. Fixed the route addition order by removing the duplicate `app.add_routes(routes)` call
3. Cleaned up the event loop management by consolidating all the setup code in the `if __name__ == '__main__':` block
4. Removed the try-except block for route addition
5. Improved the code organization and removed unnecessary whitespace

The changes have been applied successfully. The main improvements are:

1. Single initialization point for the application
2. Cleaner route addition
3. Better organized SSL and port reuse configuration
4. Proper event loop management through `web.run_app`

The application should now run more reliably and with better organization. Is there anything specific you'd like me to explain about the changes?

---



---

