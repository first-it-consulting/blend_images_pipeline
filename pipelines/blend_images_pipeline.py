"""
title: Dual-Node Blender (OpenAI Images API, Multi-Variant, Compact Traits)
author: first-it-consulting.de
description: Uses Llama 3.2 Vision to extract compact visual traits (JSON) from 2 images, then generates multiple photorealistic composite candidates via Ollama OpenAI-compatible /v1/images/generations. Stores results locally or on S3/MinIO.
date: 2026-02-06
license: MIT
version: 1.0
requirements: requests, pydantic, boto3
"""

import requests
import json
import re
import base64
import os
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Union, Generator, Iterator, List


class Pipeline:
    class Valves(BaseModel):
        # Vision (Ollama native chat endpoint)
        vision_url: str = Field(default="http://localhost:11434")
        vision_model: str = Field(default="llama3.2-vision:latest")

        # Image generation (Ollama OpenAI-compatible endpoint)
        gen_url: str = Field(default="http://localhost:11434")
        gen_model: str = Field(default="x/flux2-klein:latest")

        # Generation controls (OpenAI images-compatible)
        gen_n: int = Field(default=6, description="How many candidates to generate")
        gen_size: str = Field(default="1024x1024", description="e.g. 512x512, 1024x1024")
        gen_response_format: str = Field(default="b64_json", description="b64_json recommended")

        # Storage options
        use_s3: bool = Field(default=False, description="Use S3/MinIO for image storage")
        s3_endpoint: str = Field(default="", description="S3/MinIO endpoint URL")
        s3_bucket: str = Field(default="morphs", description="S3 bucket name")
        s3_access_key: str = Field(default="", description="S3 access key")
        s3_secret_key: str = Field(default="", description="S3 secret key")
        s3_public_url: str = Field(default="", description="Public URL for S3 objects")

    def __init__(self):
        self.name = "Dual-Node Blender images"
        self.valves = self.Valves()

    # ---------- helpers ----------

    def _extract_user_instruction_and_images(self, body: dict):
        messages = body.get("messages", [])
        images = []
        user_instruction = ""

        if not messages:
            return user_instruction, images

        last_msg = messages[-1]
        content = last_msg.get("content", "")

        # Text
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    user_instruction += item.get("text", "")
        else:
            user_instruction = content or ""

        # Images
        if "images" in last_msg:
            images = last_msg["images"] or []
        elif isinstance(content, list):
            for item in content:
                if item.get("type") == "image_url":
                    images.append({"url": item["image_url"]["url"]})

        return user_instruction.strip(), images

    def _to_b64_payload(self, img_url_or_b64: str) -> str:
        """
        Open WebUI often sends: data:image/png;base64,AAAA...
        Vision endpoint wants just the base64 chunk.
        """
        s = str(img_url_or_b64)
        if "," in s and "base64" in s[:60]:
            return s.split(",", 1)[-1]
        return s

    def _safe_json_from_text(self, text: str) -> dict:
        """
        Attempts to parse JSON even if the model wraps it in markdown fences.
        """
        t = (text or "").strip()

        # Remove ```json fences if present
        t = re.sub(r"^```json\s*", "", t, flags=re.IGNORECASE).strip()
        t = re.sub(r"^```\s*", "", t).strip()
        t = re.sub(r"\s*```$", "", t).strip()

        # Try direct parse
        try:
            return json.loads(t)
        except Exception:
            pass

        # Try to extract first {...} block
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass

        # Fallback: return raw text
        return {"raw": t}

    def _detect_subject_type(self, user_instruction: str) -> str:
        s = (user_instruction or "").lower()
        if any(w in s for w in ["baby", "infant", "child", "kid", "teen", "adult", "person", "portrait"]):
            return "a person"
        if any(w in s for w in ["dog", "cat", "pet", "animal", "horse", "bird"]):
            return "an animal"
        if any(w in s for w in ["landscape", "scene", "city", "interior", "exterior"]):
            return "a scene"
        return "a subject"

    def _traits_to_compact_line(self, traits: dict) -> str:
        """
        Turn traits dict into a compact, low-noise line for prompting.
        Keep it short to reduce "instruction soup".
        """
        if not isinstance(traits, dict):
            return str(traits)

        if "raw" in traits and len(traits) == 1:
            return traits["raw"]

        keys_order = [
            "primary_subject",
            "color_palette",
            "dominant_textures",
            "scene_type",
            "lighting",
            "composition",
            "notable_features",
            "style",
        ]
        parts = []
        for k in keys_order:
            v = traits.get(k)
            if v:
                parts.append(f"{k.replace('_',' ')}: {v}")
        return "; ".join(parts) if parts else json.dumps(traits, ensure_ascii=False)

    def _store_image_bytes(self, image_data: bytes, filename: str) -> str:
        """
        Save to S3/MinIO or local static dir and return a URL.
        """
        if self.valves.use_s3:
            try:
                import boto3
                from botocore.client import Config
                from botocore.exceptions import ClientError

                endpoint = self.valves.s3_endpoint
                if not endpoint.startswith("http"):
                    endpoint = f"http://{endpoint}"

                s3_client = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    aws_access_key_id=self.valves.s3_access_key,
                    aws_secret_access_key=self.valves.s3_secret_key,
                    region_name="us-east-1",
                    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
                    verify=False,
                )

                s3_client.put_object(
                    Bucket=self.valves.s3_bucket,
                    Key=filename,
                    Body=image_data,
                    ContentType="image/png",
                )

                if self.valves.s3_public_url:
                    return f"{self.valves.s3_public_url}/{filename}"

                return s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.valves.s3_bucket, "Key": filename},
                    ExpiresIn=3600,
                )

            except ImportError:
                raise RuntimeError("boto3 not installed. Install with: pip install boto3")
            except Exception as e:
                raise RuntimeError(f"S3 upload error: {str(e)}")

        # Local static
        static_dir = os.environ.get("PIPELINES_STATIC_DIR", "/app/static")
        morphs_dir = os.path.join(static_dir, "morphs")
        os.makedirs(morphs_dir, exist_ok=True)

        filepath = os.path.join(morphs_dir, filename)
        with open(filepath, "wb") as f:
            f.write(image_data)

        static_server_url = os.environ.get("STATIC_SERVER_URL", "http://localhost:9099")
        return f"{static_server_url}/morphs/{filename}"

    # ---------- main pipeline ----------

    def pipe(self, body: dict, **kwargs) -> Union[str, Generator, Iterator]:
        user_instruction, images = self._extract_user_instruction_and_images(body)

        if len(images) < 2:
            yield "Please upload two images to morph."
            return

        try:
            # ---- Phase 1: vision -> compact JSON traits ----
            traits = []
            for i, img in enumerate(images[:2]):
                yield f"STAGED: Analyzing image {i+1}..."

                img_url = img.get("url", "") if isinstance(img, dict) else img
                img_b64 = self._to_b64_payload(img_url)

                vision_prompt = (
                    "Return ONLY valid JSON (no markdown) describing visible traits and attributes in the image.\n"
                    "Keys: primary_subject, color_palette, dominant_textures, scene_type, lighting, composition, notable_features, style.\n"
                    "Keep each value short (1-8 words). No opinions, avoid stylistic instructions.\n\n"
                    "Example response:\n"
                    '{"primary_subject": "cat", "color_palette": "warm browns and creams", "dominant_textures": "soft fur", "scene_type": "indoor close-up", '
                    '"lighting": "soft window light", "composition": "centered, tight crop", "notable_features": "one ear slightly bent", "style": "photorealistic"}'
                )

                resp = requests.post(
                    f"{self.valves.vision_url}/api/chat",
                    json={
                        "model": self.valves.vision_model,
                        "messages": [{"role": "user", "content": vision_prompt, "images": [img_b64]}],
                        "stream": False,
                    },
                    timeout=300,
                ).json()

                text = (resp.get("message") or {}).get("content", "")
                traits.append(self._safe_json_from_text(text))

            p1 = self._traits_to_compact_line(traits[0])
            p2 = self._traits_to_compact_line(traits[1])

            # ---- Phase 2: short, photo-biased prompt ----
            subject_type = self._detect_subject_type(user_instruction)

            # Keep prompt short; long instruction lists often reduce realism.
            morph_prompt = (
                f"Photorealistic RAW image of the subject. "
                f"Composite of attributes from both input images.\n"
                f"Image 1 traits: {p1}\n"
                f"Image 2 traits: {p2}\n"
                "Combine colors, textures, shapes, and composition elements naturally. "
                "Preserve realistic materials, proportions, and lighting appropriate to the subject and scene. "
                "Neutral background unless the scene suggests otherwise, natural lighting, accurate depth of field, and subtle film grain for realism. "
                "Avoid CGI, 3D renderings, illustrations, or obviously synthetic artifacts."
            )

            # Allow user instruction, but keep it clearly separated and short
            if user_instruction and len(user_instruction) > 2:
                morph_prompt += f"\nUser preferences: {user_instruction}"

            yield "STAGED: Generating candidates..."

            # ---- Phase 3: OpenAI-compatible images generation ----
            # OpenAI compatibility endpoint:
            # POST {ollama}/v1/images/generations
            payload = {
                "model": self.valves.gen_model,
                "prompt": morph_prompt,
                "n": int(self.valves.gen_n),
                "size": self.valves.gen_size,
                "response_format": self.valves.gen_response_format,  # "b64_json"
            }

            r = requests.post(
                f"{self.valves.gen_url}/v1/images/generations",
                json=payload,
                timeout=600,
            )
            r.raise_for_status()
            gen_resp = r.json()

            data_list = gen_resp.get("data") or []
            if not data_list:
                yield f"Error: No images returned. Raw response: {json.dumps(gen_resp)[:1200]}"
                return

            # ---- Phase 4: store + display all candidates ----
            yield "STAGED: Saving results..."

            out_links: List[str] = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            for idx, item in enumerate(data_list, start=1):
                b64 = item.get("b64_json")
                if not b64:
                    # Some servers might return {url: ...} instead; handle minimally
                    url = item.get("url")
                    if url:
                        out_links.append(url)
                    continue

                image_bytes = base64.b64decode(re.sub(r"[\n\s]", "", b64))
                filename = f"morph_{timestamp}_{idx:02d}.png"
                url = self._store_image_bytes(image_bytes, filename)
                out_links.append(url)

            if not out_links:
                yield "Error: Could not decode/store generated images."
                return

            # Render as a small gallery
            md = []
            md.append("\n\n### Morph Results (multiple candidates)\n")
            md.append(f"Model: `{self.valves.gen_model}`  \nSize: `{self.valves.gen_size}`  \nCount: `{len(out_links)}`\n")
            md.append("Prompt used (compact):\n")
            md.append(f"```text\n{morph_prompt}\n```\n")
            for i, url in enumerate(out_links, start=1):
                md.append(f"Candidate {i}:\n\n![]({url})\n")

            yield "\n".join(md)

        except Exception as e:
            yield f"\nPipeline error: {str(e)}"