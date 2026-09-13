# MiniMax H3 FL2VA on RunPod

An on-demand RunPod Serverless worker for generating talking-head UGC videos from an opening image and spoken copy. MiniMax H3 FL2VA generates video and synchronized stereo audio together.

## RunPod configuration

- Queue-based Serverless endpoint with **4× H100 80 GB** per worker
- Minimum workers: **0** (no idle GPU billing)
- Maximum workers: **1**
- Idle timeout: **5 seconds**
- FlashBoot: enabled
- Execution timeout: 60 minutes

Set the endpoint's cached model to `MiniMaxAI/MiniMax-H3`. H3 is a 498 GB repository, and RunPod does not bill the cache download itself. A first cold start can still be long while FL2VA loads into GPU memory. RunPod bills initializing and running workers, but not a fully scaled-down endpoint.

## Request format

```json
{
  "input": {
    "image": "https://example.com/portrait.jpg",
    "dialogue": "Eu testei isso por sete dias e percebi uma diferença que não esperava.",
    "seconds": 15,
    "language": "Brazilian Portuguese",
    "aspect_ratio": "9:16",
    "output_upload_url": "https://storage.example.com/presigned-put-url",
    "output_url": "https://storage.example.com/final-video.mp4"
  }
}
```

Submit it to `POST https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/run`. `image` may be an HTTPS URL or a data URI. Dialogue is capped at 40 words for this 15-second test. `direction` can override the default performance/camera prompt. Production calls should supply a presigned `output_upload_url`; inline base64 is supported only below 18 MB.

## Prompt pattern for talking-head UGC

State the format and camera first, then identity/continuity, exact spoken dialogue, delivery, body motion, and sound. For example:

> Vertical 9:16 handheld smartphone UGC selfie, single continuous medium close-up. Preserve the woman’s identity, face, hair, clothes, and background from the supplied first frame. She maintains natural eye contact with the phone lens and says in Brazilian Portuguese: “YOUR SCRIPT.” Warm conversational delivery, realistic lip synchronization, natural blinking, tiny head nods and subtle breathing. Slight handheld micro-movement, soft window light, realistic indoor room tone. No cuts, no captions, no music, no extra people, no face distortion.

FL2VA uses the uploaded image as the literal first frame. If you later want a looser identity/style reference rather than an exact first frame, deploy the separate Ref2VA checkpoint.

## Operational notes

- Supported duration is 4–15 seconds; output is 24 fps with 32 kHz stereo audio.
- RunPod authenticates endpoint requests using `RUN_POD_API_KEY`; the worker needs no public port or separate API key.
- Store `RUNPOD_ENDPOINT_ID` beside `RUN_POD_API_KEY` in the app environment after deployment.
- Review the MiniMax H3 Community License before commercial use.
