FROM node:lts-alpine AS builder

WORKDIR /metube
COPY ui ./
RUN npm ci && \
    node_modules/.bin/ng build --configuration production


FROM python:3.11-alpine

WORKDIR /app

COPY Pipfile* docker-entrypoint.sh ./

# Use sed to strip carriage-return characters from the entrypoint script (in case building on Windows)
# Install dependencies
RUN sed -i 's/\r$//g' docker-entrypoint.sh && \
    chmod +x docker-entrypoint.sh && \
    apk add --update ffmpeg aria2 coreutils shadow su-exec curl tini && \
    apk add --update --virtual .build-deps gcc g++ musl-dev && \
    pip install --no-cache-dir pipenv && \
    pipenv install --system --deploy --clear && \
    pip uninstall pipenv -y && \
    apk del .build-deps && \
    rm -rf /var/cache/apk/* && \
    mkdir /.cache && chmod 777 /.cache && \
    mkdir -p /app/logs && chmod 777 /app/logs

COPY app ./app
COPY --from=builder /metube/dist/metube ./ui/dist/metube

# Combined ENV declarations
ENV UID=1000 \
    GID=1000 \
    UMASK=022 \
    DOWNLOAD_DIR=/downloads \
    STATE_DIR=/downloads/.metube \
    TEMP_DIR=/downloads

VOLUME /downloads
EXPOSE 8081
ENTRYPOINT ["/sbin/tini", "-g", "--", "./docker-entrypoint.sh"]
