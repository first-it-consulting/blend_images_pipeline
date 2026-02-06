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

---

## Example — Urban Alley + Space Cat (demo)

This example demonstrates how the pipeline combines two very different images into a single photorealistic composite. The input images for this demo were used locally (see `doss/img/` on the developer machine) and are **NOT** checked into this repository.

The resulting composite is uploaded to the configured S3/MinIO bucket (if `use_s3` is enabled). In this example the result was stored in the pipeline's S3 location; replace `s3_public_url` in your valves configuration to preview results publicly. To preview the example images locally, run the included static server (`python3 static_server.py`) or place files under `static/morphs/`.

**Input images**

- **Image 1** (`doss/img/image1.png`): dimly lit urban alley, wet pavement, muted/dark palette with pops of red and green.  
- **Image 2** (`doss/img/image2.jpg`): a vibrant orange cat in a space suit floating in space, highly detailed textures and bright colors.

**User prompt (as provided)**

> blend this both images

**Filter / Vision extraction result (example)**

Image 1 traits: **Image Summary**

This image captures a dimly lit alleyway in a densely populated urban area, characterized by a predominantly dark color palette with subtle pops of red and green.

**Foreground and Background**
The alleyway is flanked by two-story buildings, with the nearest building on the left featuring a partially visible sign and a door, while the building on the right has a door with a red sign above it. The alleyway is paved with a dark, wet surface, likely due to recent rainfall. In the distance, a car can be seen driving away from the camera.

**Context and Location**
The image appears to be set in a densely populated urban area, with the alleyway serving as a narrow passageway between the two buildings. The presence of a car in the distance suggests that the alleyway is part of a larger network of streets and roads.

**Mood and Atmosphere**
The dimly lit alleyway creates a sense of mystery and intrigue, while the presence of a car in the distance adds a sense of activity and movement to the scene. The overall mood of the image is one of urban grittiness and intensity.

---

Image 2 traits: **Cat in space (summary)**

The image features a cat dressed in a space suit, floating in space. The cat's fur is a vibrant orange color with white patches on its face, chest, and paws. Its eyes are large and round, with a curious expression. The cat's mouth is slightly open, revealing its pink tongue.

The cat's space suit is a metallic gray color with a distinctive red, green, and blue pattern on the chest. The suit has a large, round helmet with a clear visor, and a small, round backpack on its back. The cat's tail is long and fluffy, with a few strands of fur sticking out of the suit's back.

The background of the image is a deep, dark blue, with a few stars and planets visible in the distance. The overall effect is one of wonder and curiosity, as if the cat is exploring the vastness of space. The image is rendered in a highly detailed, realistic style, with a focus on texture and color. The cat's fur and the space suit's materials are both highly detailed, giving the image a sense of depth and realism. The use of bright, vibrant colors adds to the sense of wonder and curiosity, making the image feel both fun and exciting.

---

**Generation prompt used (constructed by the pipeline)**

```
Photorealistic RAW image of the subject. Composite of attributes from both input images.
Image 1 traits: **Image Summary**
Image 2 traits: **Cat in space (summary)**
Combine colors, textures, shapes, and composition elements naturally. Preserve realistic materials, proportions, and lighting appropriate to the subject and scene. Neutral background unless the scene suggests otherwise, natural lighting, accurate depth of field, and subtle film grain for realism. Avoid CGI, 3D renderings, illustrations, or obviously synthetic artifacts.
User preferences: blend this both images
```

**Models used**

- Vision extraction: `llama3.2-vision:latest` (Ollama vision model)
- Image generation: `x/flux2-klein:latest` (Ollama image-generation model via the experimental `/v1/images/generations` endpoint)

**Result**

The generated composite demonstrates a fusion of the alleyway's mood and materials with the cat-in-space subject: colors and textures are blended while attempting to preserve realistic lighting and depth. The generated composite was uploaded to the pipeline's configured S3/MinIO location (see `s3_public_url` in `valves.json`) and therefore is not committed to this repository. To preview a locally-generated result, run the static server or copy the file into `static/morphs/` and reload the gallery.

---

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