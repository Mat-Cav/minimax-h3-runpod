# MiniMax H3 FL2VA on RunPod

A small authenticated web app and HTTP API for generating talking-head UGC videos from an opening image and a prompt. MiniMax H3 FL2VA generates the video and synchronized stereo audio together.

## Recommended RunPod configuration

- Pod (not Serverless): **4× H100 80 GB**, Secure Cloud
- Container image: build this `Dockerfile`
- Container disk: 30 GB
- Persistent/network volume: **550 GB** mounted at `/workspace`
- Exposed port: `8000/http`
- Environment: `FL2VA_API_KEY=<long random value>`, `H3_PROFILE=h100x4`

The first boot downloads a very large checkpoint into `/workspace/huggingface`. Keep that path on persistent storage. For lower-cost experimentation, `rtx4090x1` is supported with INT8 plus CPU offload, but expect far slower generation and ensure the host has enough RAM/NVMe. The validated two-card alternative (`rtx5090x2`) requires roughly 384 GB host RAM.

## Run locally / build

```bash
docker build -t minimax-h3-fl2va .
docker run --gpus all --ipc=host -p 8000:8000 \
  -v "$PWD/hf-cache:/workspace/huggingface" \
  -e FL2VA_API_KEY=change-me \
  -e H3_PROFILE=h100x4 \
  minimax-h3-fl2va
```

Open `http://localhost:8000`. The UI submits `POST /generate` using the `X-API-Key` header.

```bash
curl -fS http://localhost:8000/generate \
  -H "X-API-Key: $FL2VA_API_KEY" \
  -F image=@portrait.jpg \
  -F seconds=5 \
  -F aspect_ratio=9:16 \
  -F 'prompt=Vertical handheld UGC selfie. The speaker looks into the lens and says in Brazilian Portuguese: “Eu testei isso por sete dias.” Natural blinking, subtle head motion, realistic room tone.' \
  -o ugc.mp4
```

## Prompt pattern for talking-head UGC

State the format and camera first, then identity/continuity, exact spoken dialogue, delivery, body motion, and sound. For example:

> Vertical 9:16 handheld smartphone UGC selfie, single continuous medium close-up. Preserve the woman’s identity, face, hair, clothes, and background from the supplied first frame. She maintains natural eye contact with the phone lens and says in Brazilian Portuguese: “YOUR SCRIPT.” Warm conversational delivery, realistic lip synchronization, natural blinking, tiny head nods and subtle breathing. Slight handheld micro-movement, soft window light, realistic indoor room tone. No cuts, no captions, no music, no extra people, no face distortion.

FL2VA uses the uploaded image as the literal first frame. If you later want a looser identity/style reference rather than an exact first frame, deploy the separate Ref2VA checkpoint.

## Operational notes

- Supported duration is 4–15 seconds; output is 24 fps with 32 kHz stereo audio.
- `GET /health` reports whether the API and underlying model server are ready.
- Do not expose port 30010 publicly; only the authenticated wrapper on port 8000 should be public.
- Review the MiniMax H3 Community License before commercial use.
