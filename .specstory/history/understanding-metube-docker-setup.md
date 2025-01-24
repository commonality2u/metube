## SpecStory

## Understanding MeTube Docker Setup (1/22/2025, 9:34:38 AM)

_**User**_

so to set this up, do just run this .sh command? or do i need to run this command and do i need to set the download path?? or just run the .sh command?? @Codebase 

bash docker run -d -p 8081:8081 -v /path/to/downloads:/downloads ghcr.io/alexta69/metube

---

_**Assistant**_

<contemplator>
Let me analyze this as a Docker deployment expert to provide a clear understanding of the setup process.

First, let's examine the provided Docker command:

```15:15:README.md
docker run -d -p 8081:8081 -v /path/to/downloads:/downloads ghcr.io/alexta69/metube
```


This command has several key components that need attention:
1. `-d`: Runs container in detached mode (background)
2. `-p 8081:8081`: Maps port 8081 from container to host
3. `-v /path/to/downloads:/downloads`: Volume mapping for downloads

The critical elements I need to consider:
1. The download path must be specified and cannot be used as-is with "/path/to/downloads"
2. The docker-entrypoint.sh is part of the container image and not something you need to run directly
3. The environment variables might need configuration

Looking at the Windows-specific configurations:

```12:17:.vscode/launch.json
            "windows": {
                "env": {
                    "DOWNLOAD_DIR": "${env:USERPROFILE}/Downloads",
                    "STATE_DIR": "${env:TEMP}",
                }
            },
```

This shows that on Windows, the default download location should be in the user's Downloads folder.

Let me think about the best approach for Windows:
1. We need a valid Windows path format
2. The path needs proper permissions
3. The path should be easily accessible to the user

The docker-entrypoint.sh is actually part of the container:

```1:19:docker-entrypoint.sh
#!/bin/sh

echo "Setting umask to ${UMASK}"
umask ${UMASK}
echo "Creating download directory (${DOWNLOAD_DIR}), state directory (${STATE_DIR}), and temp dir (${TEMP_DIR})"
mkdir -p "${DOWNLOAD_DIR}" "${STATE_DIR}" "${TEMP_DIR}"

if [ `id -u` -eq 0 ] && [ `id -g` -eq 0 ]; then
    if [ "${UID}" -eq 0 ]; then
        echo "Warning: it is not recommended to run as root user, please check your setting of the UID environment variable"
    fi
    echo "Changing ownership of download and state directories to ${UID}:${GID}"
    chown -R "${UID}":"${GID}" /app "${DOWNLOAD_DIR}" "${STATE_DIR}" "${TEMP_DIR}"
    echo "Running MeTube as user ${UID}:${GID}"
    su-exec "${UID}":"${GID}" python3 app/main.py
else
    echo "User set by docker; running MeTube as `id -u`:`id -g`"
    python3 app/main.py
fi
```

This script handles internal container setup and doesn't need to be run manually - it's automatically executed when the container starts.

</contemplator>

<final_answer>
For Windows setup, you need to modify the Docker command - you can't just run the .sh file. Here's the correct setup process:

1. Create a folder for your downloads (e.g., D:\Downloads\metube)

2. Run this modified Docker command (adjust the path to match your created folder):
```bash
docker run -d -p 8081:8081 -v D:/Downloads/metube:/downloads ghcr.io/alexta69/metube
```

Key points:
- Use forward slashes (/) even in Windows paths
- Specify a real path instead of "/path/to/downloads"
- The .sh file is internal to the container - don't try to run it directly
- After running the command, access MeTube at http://localhost:8081

Optional: If you want to customize any settings, you can add environment variables with -e flags:
```bash
docker run -d -p 8081:8081 -v D:/Downloads/metube:/downloads -e DEFAULT_THEME=dark ghcr.io/alexta69/metube
```

The docker-entrypoint.sh will run automatically inside the container - you don't need to do anything with it directly.

---

_**User**_

here is the download folder where we will download the contents from the metube - "D:\Documents\Boxing_Legends_Videos_downloads" , but this is not the same directory where the metube app is running. 

---

_**Assistant**_



<contemplator>
Let me analyze this as a Docker volume mapping expert.

The beauty of Docker volume mapping is that the download location can be completely separate from where the application is running. This is actually a good practice for organization.

Let's examine the path:
`D:\Documents\Boxing_Legends_Videos_downloads`

For Docker volume mapping, we need to consider:
1. Windows paths need to be converted to Docker-compatible format
2. Backslashes need to be changed to forward slashes
3. The path needs to exist before running the container

Looking at the Docker configuration:
```dockerfile
ENV DOWNLOAD_DIR /downloads
VOLUME /downloads
```

This shows that inside the container, everything will go to `/downloads`, and we just need to map this to our Windows path.

The path conversion would be:
`D:\Documents\Boxing_Legends_Videos_downloads` → `D:/Documents/Boxing_Legends_Videos_downloads`

Let me verify this against the Windows installation guide:
```yaml:.specstory/history/windows-installation-guide-for-metube.md
volumes:
      - D:/Downloads/metube:/downloads
```

This confirms the format we should use for Windows paths.

</contemplator>

<final_answer>
Here's the correct Docker command for your specific download location:

```bash
docker run -d -p 8081:8081 -v D:/Documents/Boxing_Legends_Videos_downloads:/downloads ghcr.io/alexta69/metube
```

Important notes:
1. Make sure the folder `D:\Documents\Boxing_Legends_Videos_downloads` exists before running the command
2. Notice how we changed backslashes (`\`) to forward slashes (`/`)
3. The location of the MeTube app itself doesn't matter - Docker will handle that
4. After running, you can access MeTube at http://localhost:8081
5. All downloads will appear in `D:\Documents\Boxing_Legends_Videos_downloads`

---

_**User**_

i got this as an error

---

_**Assistant**_

<contemplator>
As a Docker networking expert, I can see this is a port conflict issue. Let's analyze the error:

`Bind for 0.0.0.0:8081 failed: port is already allocated`

This error occurs when:
1. A previous instance of MeTube is already running on port 8081
2. Some other application is using port 8081
3. The first command attempt actually succeeded but the second command failed

Looking at your command history:
1. You tried to run the command twice
2. The first command returned a container ID: `244477dc2f5a1702855162a7babaa4dc0cb831d1439484f8ecfd47d41a3ab3e1`
3. This suggests the container is actually running from the first attempt

Let me think about the verification and resolution steps:
1. We need to check running containers
2. We might need to stop the existing container
3. We could use a different port if needed

</contemplator>

<final_answer>
First, let's check if MeTube is already running. Run this command:
```bash
docker ps
```

If you see a MeTube container running, you have two options:

1. Stop the existing container and reuse port 8081:
```bash
docker stop 244477dc2f5a  # Using the first few characters of your container ID is sufficient
docker rm 244477dc2f5a    # Remove the stopped container
# Then run your original command again
docker run -d -p 8081:8081 -v D:/Documents/Boxing_Legends_Videos_downloads:/downloads ghcr.io/alexta69/metube
```

2. OR use a different port (e.g., 8082):
```bash
docker run -d -p 8082:8081 -v D:/Documents/Boxing_Legends_Videos_downloads:/downloads ghcr.io/alexta69/metube
```
Then access MeTube at http://localhost:8082

Choose option 1 if you want to keep using port 8081, or option 2 if you want to run multiple instances of MeTube.

---

_**User**_

@ytdl.py what seems to be the issue? 

---

_**Assistant**_

Looking at the error logs, there are several related issues in the ytdl.py implementation:

1. First Error - Playlist Item Limit:
```python
TypeError: '>' not supported between instances of 'NoneType' and 'int'
```
This occurs because `playlist_item_limit` is being passed as `None` but the code tries to compare it with an integer.

2. Second Error - Missing Start Method:
```python
AttributeError: 'DownloadInfo' object has no attribute 'start'
```
The code is trying to call `download.start()` but it's operating on a `DownloadInfo` object instead of a `Download` object.

3. Third Error - Missing Info Attribute:
```python
AttributeError: 'DownloadInfo' object has no attribute 'info'
```
The code expects `download.info` but the object doesn't have this attribute.

Here's how to fix these issues:

```python:app/ytdl.py
# ... existing code ...

async def __add_entry(self, entry, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already):
    # ... existing code ...
    
    # Fix playlist_item_limit comparison
    if playlist_item_limit is not None and playlist_item_limit > 0:
        log.info(f'playlist limit is set. Processing only first {playlist_item_limit} entries')
        ytdl_options['playlistend'] = playlist_item_limit

    # Fix Download object creation
    if auto_start is True:
        download = Download(dldirectory, self.config.TEMP_DIR, output, output_chapter, quality, format, ytdl_options, dl)
        self.queue.put(download)  # Store Download object, not DownloadInfo
        self.event.set()
    else:
        download = Download(dldirectory, self.config.TEMP_DIR, output, output_chapter, quality, format, ytdl_options, dl)
        self.queue.put(download)  # Store Download object, not DownloadInfo
    await self.notifier.added(dl)
    
    return {'status': 'ok'}

# ... existing code ...

def get(self):
    """Modified to handle both Download and DownloadInfo objects"""
    queue_items = []
    done_items = []
    
    for k, v in self.queue.items():
        if hasattr(v, 'info'):
            queue_items.append((k, v.info))
        else:
            queue_items.append((k, v))  # Fallback if it's a DownloadInfo
            
    for k, v in self.done.items():
        if hasattr(v, 'info'):
            done_items.append((k, v.info))
        else:
            done_items.append((k, v))  # Fallback if it's a DownloadInfo
            
    return (queue_items, done_items)
```

The main issues were:
1. Not checking if `playlist_item_limit` is None before comparison
2. Storing `DownloadInfo` objects instead of `Download` objects in the queue
3. Not properly handling the case where queue items might be either `Download` or `DownloadInfo` objects

These changes should resolve the errors you're seeing. The code now:
- Safely handles None values for playlist_item_limit
- Creates proper Download objects before storing them in the queue
- Handles both Download and DownloadInfo objects when getting queue items

---

_**User**_

where do i replace the following in the @main.py ?

# Replace the existing web.run_app() calls with this pattern:
async def main():
    await web.run_app(init(), host=config.HOST, port=int(config.PORT))

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())

---

_**Assistant**_

In the `main.py` file, you need to replace the code at the very bottom. Here's the change:

```python:app/main.py
# ... existing code ...

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log.info(f"Listening on {config.HOST}:{config.PORT}")

    async def init():
        # Initialize the download queue and import saved items
        global dqueue
        dqueue = DownloadQueue(config, Notifier())
        await dqueue._DownloadQueue__import_queue()  # Force import saved items
        return app

    # Replace everything below this line
    async def main():
        if config.HTTPS:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(certfile=config.CERTFILE, keyfile=config.KEYFILE)
            await web.run_app(init(), host=config.HOST, port=int(config.PORT), ssl_context=ssl_context)
        else:
            await web.run_app(init(), host=config.HOST, port=int(config.PORT))

    asyncio.run(main())
```

The key changes are:
1. Wrapped the web.run_app() calls in an async main() function
2. Changed from direct web.run_app() to await web.run_app()
3. Used asyncio.run(main()) to run the async main function

This pattern provides better async/await handling and cleaner shutdown behavior. The rest of your code remains unchanged.

---

_**User**_

what are the main working files from this project related to the yt-dlp library, downloading the specific file types, organization, json cleaning?? @Codebase I want to understand which files i need to take to a new project. 

---

_**Assistant**_



---



---

