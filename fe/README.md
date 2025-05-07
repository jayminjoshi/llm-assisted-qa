# Streamlit Front End


# Build

## Local
```bash
docker build --build-arg ENV=docker-local -t fe .
```

## Cloud
```bash
docker build --build-arg ENV=docker-cloud -t fe --no-cache .
```

# Run

## Local
```bash
docker run \
-p 8501:8501 \
--mount type=bind,source="$(pwd)"/config/config.toml,target=/app/config/config.toml,readonly \
--mount type=bind,source="$HOME/.config/gcloud/application_default_credentials.json",target=/gcp/creds.json,readonly \
--name fe \
--env GOOGLE_APPLICATION_CREDENTIALS=/gcp/creds.json \
--env GOOGLE_CLOUD_PROJECT=xxx \
--add-host host.docker.internal:host-gateway \
--rm \
fe \
main.py --server.port=8501 --server.address=0.0.0.0 --server.fileWatcherType=None --logger.level=debug --server.maxUploadSize=100
```

## Prod
```bash
docker run \
-p 8501:8501 \
--mount type=bind,source="$HOME"/fe/config/config.toml,target=/app/config/config.toml,readonly \
--mount type=bind,source="$HOME"/gcp_creds.json,target=/gcp/creds.json,readonly \
--env GOOGLE_APPLICATION_CREDENTIALS=/gcp/creds.json \
--env GOOGLE_CLOUD_PROJECT=xxx \
--add-host host.docker.internal:host-gateway \
--name fe \
-d \
fe \
main.py --server.port=8501 --server.address=0.0.0.0 --server.fileWatcherType=None --logger.level=debug --server.maxUploadSize=100
```
