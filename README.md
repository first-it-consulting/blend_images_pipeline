# Blend Images Pipeline (Open WebUI)

Generate multiple photorealistic blended-face candidates from two parent images using:

- **Vision model** (Ollama native chat API) to extract compact facial traits
- **OpenAI-compatible image generation** (Ollama `/v1/images/generations`)
- **Local or S3/MinIO** storage for outputs

This repository contains a single Open WebUI pipeline:

- [pipelines/blend_images_pipeline.py](pipelines/blend_images_pipeline.py)

## Features

- Dual-stage pipeline: trait extraction → image generation
- Multiple candidate outputs per request
- Local static file hosting or S3/MinIO upload
- Compatible with Open WebUI pipelines container

## How It Works

1. **Extract traits** from two uploaded images using a vision model.
2. **Generate prompt** from compact traits + optional user preferences.
3. **Create images** via OpenAI-compatible image generation endpoint.
4. **Store results** locally or on S3/MinIO and return a gallery.

## Requirements

- Open WebUI Pipelines container
- Ollama with a vision model (e.g., `llama3.2-vision`)
- Ollama with an image model that supports OpenAI-compatible images API

Optional:

- S3-compatible storage (MinIO or AWS S3)

## Configuration

The pipeline uses **Valves** for configuration inside Open WebUI. Default values are in the pipeline code.

### Valves (Key Settings)

- `vision_url`: Ollama endpoint for vision chat
- `vision_model`: vision model name
- `gen_url`: Ollama endpoint for image generation
- `gen_model`: image generation model name
- `gen_n`: number of images to generate
- `gen_size`: image size, e.g. `1024x1024`
- `use_s3`: enable S3/MinIO storage
- `s3_endpoint`, `s3_bucket`, `s3_access_key`, `s3_secret_key`, `s3_public_url`

### Environment Variables

- `PIPELINES_STATIC_DIR`: local static output dir (default `/app/static`)
- `STATIC_SERVER_URL`: base URL for local static server

## Local Development (Pipelines Container)

Run the Open WebUI pipelines container with this repo mounted:

```bash
docker stop pipelines-dev && \
docker run --rm -p 9099:9099 \
  -e PIPELINES_STATIC_DIR=/app/static \
  -e PIPELINE_URL=http://localhost:9099 \
  -v $(pwd)/pipelines:/app/pipelines \
  -v $(pwd)/static:/app/static \
  --name pipelines-dev \
  ghcr.io/open-webui/pipelines:main
```

## Static File Server (Optional)

If you want local image URLs that can be opened by clients, run the included static server:

```bash
python3 static_server.py
```

Or run it in Docker (simple, no image build needed):

```bash
docker run --rm -p 9098:9098 \
  -v $(pwd)/static:/app/static \
  -w /app \
  python:3.11-slim \
  python /app/../static_server.py
```

By default it serves [static](static) on port `9098` and exposes images at:

```
http://localhost:9098/morphs/
```

To make the pipeline return those URLs, set:

```
STATIC_SERVER_URL=http://localhost:9098
```

You can pass this into the pipelines container as an environment variable if needed.

## S3/MinIO Setup

If using MinIO, ensure your bucket policy allows public reads or provide a `s3_public_url`.
Example policy setup (MinIO client):

```bash
s3cmd setpolicy ./bucket-policy.json s3://morphs
```

## Folder Structure

```
pipelines/
  blend_images_pipeline.py
static/
  morphs/               # generated images (local mode)
k8s/                    # optional k8s manifests
```

## Notes

- The pipeline expects **exactly two images** in the user request.
- Outputs include a small markdown gallery with all candidates.
- For best results, keep user instructions short and specific.

## License

No license specified. Add one if you intend to distribute this publicly.