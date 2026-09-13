import base64
import os
import secrets
import time
from typing import Any

import httpx
import runpod

SGLANG_URL = os.getenv("SGLANG_URL", "http://127.0.0.1:30010").rstrip("/")
MODEL_READY_TIMEOUT = int(os.getenv("MODEL_READY_TIMEOUT", "3600"))
GENERATION_TIMEOUT = int(os.getenv("GENERATION_TIMEOUT", "1800"))
MAX_DIALOGUE_WORDS = int(os.getenv("MAX_DIALOGUE_WORDS", "40"))
MAX_INLINE_OUTPUT_BYTES = int(os.getenv("MAX_INLINE_OUTPUT_BYTES", str(18 * 1024 * 1024)))


def _wait_for_model(client: httpx.Client) -> None:
    deadline = time.monotonic() + MODEL_READY_TIMEOUT
    while time.monotonic() < deadline:
        try:
            if client.get(f"{SGLANG_URL}/health", timeout=5).is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise TimeoutError("MiniMax H3 did not become ready before the initialization timeout")


def _validate(job_input: dict[str, Any]) -> tuple[str, str, int, str]:
    image = job_input.get("image")
    dialogue = job_input.get("dialogue")
    seconds = job_input.get("seconds", 15)
    aspect_ratio = job_input.get("aspect_ratio", "9:16")
    if not isinstance(image, str) or not (image.startswith("https://") or image.startswith("data:image/")):
        raise ValueError("image must be an HTTPS URL or a data:image/... URI")
    if not isinstance(dialogue, str) or not dialogue.strip():
        raise ValueError("dialogue is required")
    if len(dialogue.split()) > MAX_DIALOGUE_WORDS:
        raise ValueError(f"dialogue is capped at {MAX_DIALOGUE_WORDS} words for a 15-second clip")
    if not isinstance(seconds, int) or not 4 <= seconds <= 15:
        raise ValueError("seconds must be an integer from 4 through 15")
    if aspect_ratio not in {"auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}:
        raise ValueError("unsupported aspect_ratio")
    return image, dialogue.strip(), seconds, aspect_ratio


def _build_prompt(job_input: dict[str, Any], dialogue: str) -> str:
    direction = job_input.get("direction") or (
        "Vertical handheld smartphone UGC selfie, one continuous medium close-up. "
        "Preserve identity, face, hair, clothing, and background from the first frame. "
        "Natural eye contact, conversational delivery, realistic lip sync, blinking, tiny head "
        "movements and breathing, soft natural light, slight handheld micro-movement, realistic "
        "room tone. No cuts, captions, music, extra people, face distortion, or transition."
    )
    return f'{direction}\nThe speaker says in {job_input.get("language", "Brazilian Portuguese")}: "{dialogue}"'


def _deliver_video(client: httpx.Client, content: bytes, job_input: dict[str, Any], video_id: str) -> dict[str, Any]:
    upload_url = job_input.get("output_upload_url")
    if upload_url:
        if not isinstance(upload_url, str) or not upload_url.startswith("https://"):
            raise ValueError("output_upload_url must be an HTTPS presigned PUT URL")
        uploaded = client.put(upload_url, content=content, headers={"Content-Type": "video/mp4"}, timeout=300)
        uploaded.raise_for_status()
        public_url = job_input.get("output_url")
        return {"video_id": video_id, "video_url": public_url if isinstance(public_url, str) else None,
                "bytes": len(content), "delivery": "uploaded"}
    if len(content) > MAX_INLINE_OUTPUT_BYTES:
        raise ValueError("Video exceeds inline response limit; provide output_upload_url and output_url")
    return {"video_id": video_id, "video_base64": base64.b64encode(content).decode("ascii"),
            "content_type": "video/mp4", "bytes": len(content), "delivery": "inline"}


def handler(job: dict[str, Any]) -> dict[str, Any]:
    job_input = job.get("input") or {}
    try:
        image, dialogue, seconds, aspect_ratio = _validate(job_input)
        with httpx.Client(timeout=60) as client:
            _wait_for_model(client)
            response = client.post(f"{SGLANG_URL}/v1/videos", json={
                "task": "fl2va", "prompt": _build_prompt(job_input, dialogue),
                "conditions": [{"type": "image", "uri": image, "role": "keyframe", "frame_index": 0}],
                "target": {"short_edge": 768, "aspect_ratio": aspect_ratio, "duration_seconds": seconds},
                "seed": job_input.get("seed", secrets.randbelow(2**31)),
            })
            response.raise_for_status()
            video_id = response.json()["id"]
            deadline = time.monotonic() + GENERATION_TIMEOUT
            while time.monotonic() < deadline:
                status_response = client.get(f"{SGLANG_URL}/v1/videos/{video_id}")
                status_response.raise_for_status()
                status = status_response.json()
                if status.get("status") == "completed":
                    video = client.get(f"{SGLANG_URL}/v1/videos/{video_id}/content", timeout=300)
                    video.raise_for_status()
                    return _deliver_video(client, video.content, job_input, video_id)
                if status.get("status") == "failed":
                    raise RuntimeError(status.get("error", "H3 generation failed"))
                time.sleep(1)
            raise TimeoutError("H3 generation timed out")
    except Exception as exc:
        return {"error": str(exc), "type": type(exc).__name__}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
