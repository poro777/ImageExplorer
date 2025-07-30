# ImageExplorer

This repository contains the backend service for the ImageExplorer application.

## What is ImageExplorer?

ImageExplorer is a self-hosted application designed to help you search and explore your local image collection using natural language. It works by:

1.  **Watching Your Folders**: You can designate one or more folders on your system for ImageExplorer to monitor.
2.  **Automatic Indexing**: The service automatically detects new or modified images in the watched folders.
3.  **AI-Powered Descriptions**: For each image, it uses a generative AI model to create a rich, descriptive text caption.
4.  **Vector-Based Search**: It stores these descriptions and image embeddings in a Milvus vector database.
5.  **Intelligent Querying**: You can search for images using natural language queries (e.g., "a dog playing in the snow"). The backend combines vector similarity search and traditional text search (BM25) to find the most relevant images from your collection.

This guide will walk you through setting up the project for local development and testing.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- **Python**: The required version is specified in the `backend/.python-version` file.
- **uv**: A fast Python package installer and resolver from Astral.
- **Docker** and **Docker Compose**: To run required services like Milvus in isolated containers.

## Development Setup

Follow these steps to get your development environment running.

### 1. Clone the Repository

First, clone the project to your local machine:

```bash
git clone <repository-url>
cd ImageExplorer
```

### 2. Start Dependent Services

The backend relies on services like Milvus, which are managed via Docker Compose. To start these services, run:

```bash
docker compose -f Docker-compose.yml up -d
```

You can verify that Milvus is running and healthy with the following command:

```bash
curl http://localhost:9091/healthz
```

A successful response will contain `"OK"`. It might take a minute for the service to become fully available.

### 3. Configure the Backend

All subsequent commands should be run from within the `backend` directory.

```bash
cd backend
```

### 4. Install Dependencies

This project uses `uv` to manage Python dependencies. To install them, run:

```bash
uv sync --locked
```
This command installs the exact versions of dependencies specified in `uv.lock` into your virtual environment.

### 5. Set Up Environment Variables

The application requires certain secrets and configuration to be provided as environment variables. Create a `.env` file in the `backend` directory:

```bash
touch .env
```

Now, open the `.env` file and add the necessary variables. For example:

```env
GENAI_API_KEY="your_secret_api_key_here"
```

This file is ignored by git, so your secrets will remain local.

### 6. Run the Development Server

To start the FastAPI application in development mode, run the following command from the `backend` directory:

```bash
uv run uvicorn main:app --reload
```

This command starts the server with auto-reload enabled. The application will be accessible at `http://localhost:8000`, and the interactive API documentation will be available at `http://localhost:8000/docs`.

## Running Tests

With the environment set up and services running, you can execute the test suite:

```bash
uv run pytest
```

## Shutting Down

When you're finished with your development session, you can stop the Docker containers:

```bash
docker compose -f Docker-compose.yml down
```