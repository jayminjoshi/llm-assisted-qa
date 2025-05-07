# Back End

## Build

### Local
```bash
docker build --build-arg ENV=docker-local -t be .
```

### Prod
```bash
docker build --build-arg ENV=docker-cloud -t be --no-cache .
```

## Run

### Local
```bash
docker run \
-p 8000:8000 \
--mount type=bind,source="$(pwd)"/app/config/config.toml,target=/app/app/config/config.toml,readonly \
--mount type=bind,source="$HOME/.config/gcloud/application_default_credentials.json",target=/gcp/creds.json,readonly \
--env GOOGLE_APPLICATION_CREDENTIALS=/gcp/creds.json \
--env GOOGLE_CLOUD_PROJECT=xxx \
--add-host host.docker.internal:host-gateway \
--name be \
--rm \
be
```

# Prod
```bash
docker run \
-p 8000:8000 \
--mount type=bind,source="$HOME"/llm-assisted-qa/be/app/config/config.toml,target=/app/app/config/config.toml,readonly \
--mount type=bind,source="$HOME"/gcp_creds.json,target=/gcp/creds.json,readonly \
--env GOOGLE_APPLICATION_CREDENTIALS=/gcp/creds.json \
--env GOOGLE_CLOUD_PROJECT=xxx \
--add-host host.docker.internal:host-gateway \
--name be \
-d \
be
```


