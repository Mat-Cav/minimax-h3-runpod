import asyncio
import base64
import os
import secrets
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

SGLANG_URL = os.getenv("SGLANG_URL", "http://127.0.0.1:30010").rstrip("/")
API_KEY = os.environ.get("FL2VA_API_KEY", "")
MAX_IMAGE_BYTES = 15 * 1024 * 1024
POLL_SECONDS = 1.0
GENERATION_TIMEOUT = 30 * 60


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not API_KEY:
        raise RuntimeError("FL2VA_API_KEY must be configured")
    app.state.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    yield
    await app.state.client.aclose()


app = FastAPI(title="MiniMax H3 FL2VA", version="1.0.0", lifespan=lifespan)


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not API_KEY or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\">
<title>FL2VA UGC Studio</title><style>
body{font:16px system-ui;background:#101114;color:#eee;max-width:760px;margin:40px auto;padding:20px}
form{display:grid;gap:14px;background:#191b20;padding:24px;border-radius:14px}textarea,input,select,button{font:inherit;padding:11px;border-radius:8px;border:1px solid #3a3e48;background:#111318;color:#fff}textarea{min-height:150px}button{background:#6c5ce7;font-weight:700;cursor:pointer}video{width:100%;margin-top:24px}small{color:#aaa}</style></head><body>
<h1>FL2VA UGC Studio</h1><p>Upload the exact opening frame and describe the performance, dialogue, camera, and sound.</p>
<form id=\"f\"><label>API key<input id=\"key\" type=\"password\" required></label><label>Opening image<input name=\"image\" type=\"file\" accept=\"image/png,image/jpeg,image/webp\" required></label><label>Prompt<textarea name=\"prompt\" required placeholder=\"Vertical handheld UGC selfie. The woman looks into the lens and says in Brazilian Portuguese: ‘...’ Natural blinking, subtle head movement...\"></textarea></label><label>Duration<select name=\"seconds\"><option>5</option><option>6</option><option>8</option><option>10</option><option>15</option></select> seconds</label><label>Aspect ratio<select name=\"aspect_ratio\"><option value=\"9:16\">9:16 vertical</option><option value=\"16:9\">16:9 horizontal</option><option value=\"1:1\">1:1 square</option><option value=\"auto\">Match image</option></select></label><button>Generate video</button><small id=\"s\"></small></form><video id=\"v\" controls></video>
<script>f.onsubmit=async e=>{e.preventDefault();s.textContent='Generating… the first run also downloads and loads the model.';v.removeAttribute('src');try{let r=await fetch('/generate',{method:'POST',headers:{'X-API-Key':key.value},body:new FormData(f)});if(!r.ok)throw Error((await r.json()).detail||r.statusText);v.src=URL.createObjectURL(await r.blob());s.textContent='Done.'}catch(x){s.textContent='Error: '+x.message}}</script></body></html>"""


@app.get("/health")
async def health() -> dict:
    try:
        response = await app.state.client.get(f"{SGLANG_URL}/health", timeout=2.0)
        ready = response.is_success
    except httpx.HTTPError:
        ready = False
    return {"api": "ok", "model_ready": ready}


@app.post("/generate", dependencies=[Depends(require_api_key)])
async def generate(
    image: UploadFile = File(...),
    prompt: str = Form(..., min_length=10, max_length=12000),
    seconds: int = Form(5, ge=4, le=15),
    aspect_ratio: str = Form("9:16"),
    seed: int | None = Form(None),
) -> Response:
    if aspect_ratio not in {"auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}:
        raise HTTPException(status_code=422, detail="Unsupported aspect ratio")
    if image.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="Use a PNG, JPEG, or WebP image")
    raw = await image.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 15 MB")

    data_uri = f"data:{image.content_type};base64,{base64.b64encode(raw).decode()}"
    payload = {
        "model": "MiniMaxAI/MiniMax-H3",
        "prompt": prompt,
        "seconds": seconds,
        "task": "fl2va",
        "conditions": [{"type": "image", "uri": data_uri, "role": "keyframe", "frame_index": 0}],
        "target": {"short_edge": 768, "aspect_ratio": aspect_ratio, "duration_seconds": float(seconds)},
        "num_outputs_per_prompt": 1,
        "num_inference_steps": 50,
        "flow_shift": 12.0,
        "audio_flow_shift": 3.0,
        "seed": seed if seed is not None else secrets.randbelow(2**31),
    }
    client: httpx.AsyncClient = app.state.client
    try:
        created = await client.post(f"{SGLANG_URL}/v1/videos", json=payload)
        created.raise_for_status()
        video_id = created.json()["id"]
        deadline = asyncio.get_running_loop().time() + GENERATION_TIMEOUT
        while asyncio.get_running_loop().time() < deadline:
            status_response = await client.get(f"{SGLANG_URL}/v1/videos/{video_id}")
            status_response.raise_for_status()
            status = status_response.json()
            if status.get("status") == "completed":
                video = await client.get(f"{SGLANG_URL}/v1/videos/{video_id}/content", timeout=120.0)
                video.raise_for_status()
                return Response(video.content, media_type="video/mp4", headers={"Content-Disposition": f'attachment; filename="fl2va-{video_id}.mp4"'})
            if status.get("status") == "failed":
                raise HTTPException(status_code=502, detail=status.get("error", "Generation failed"))
            await asyncio.sleep(POLL_SECONDS)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Model service unavailable: {exc}") from exc
    raise HTTPException(status_code=504, detail="Generation timed out")
