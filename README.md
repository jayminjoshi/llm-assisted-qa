![Alt text](fe/assets/Logo.jpg?raw=true "Title")

# LLM-Assisted Q&A Service

A modern web application that provides an intelligent Q&A service powered by Langraph. The application consists of a Streamlit-based frontend and a Python-based backend, both containerized using Docker.

Intially this was built for RFP based Q&A, but it can be used for any type of document.

## Project Structure

```
├── fe/ # Frontend application (Streamlit)
│ ├── auth/ # Authentication components
│ ├── components/ # UI components
│ ├── utils/ # Utility functions
│ ├── processing/ # Data processing logic
│ ├── config/ # Configuration files
│ └── assets/ # Static assets
└── be/ # Backend application
└── app/ # Backend application code
```

## Features

- Modern web interface built with Streamlit
- Secure authentication system
- Project-based organization of Q&A interactions
- File upload and processing capabilities
- RFP (Request for Proposal) processing and management
- Docker containerization for easy deployment

## Prerequisites

- Docker
- Google Cloud Platform account (for production deployment)
- Python 3.x

## Getting Started

### Frontend Setup

1. Build the frontend Docker image:
```bash
# For local development
docker build --build-arg ENV=docker-local -t fe .

# For production
docker build --build-arg ENV=docker-cloud -t fe --no-cache .
```

2. Run the frontend container:
```bash
# Local development
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

### Backend Setup

1. Build the backend Docker image:
```bash
# For local development
docker build --build-arg ENV=docker-local -t be .

# For production
docker build --build-arg ENV=docker-cloud -t be --no-cache .
```

2. Run the backend container:
```bash
# Local development
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

## Configuration

The application uses configuration files located in:
- Frontend: `fe/config/config.toml`
- Backend: `be/app/config/config.toml`

Make sure to set up these configuration files with appropriate values for your environment.

## Development

The application is built with:
- Frontend: Streamlit
- Backend: Python
- Containerization: Docker
- Deployed on Google Cloud Platform