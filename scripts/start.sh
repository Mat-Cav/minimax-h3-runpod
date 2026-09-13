#!/usr/bin/env bash
set -Eeuo pipefail

: "${FL2VA_API_KEY:?Set FL2VA_API_KEY to protect the public API}"

mkdir -p "${HF_HOME:-/workspace/huggingface}"

profile="${H3_PROFILE:-h100x4}"
case "$profile" in
  h100x4)
    h3_args=(
      --num-gpus 4
      --tp-size 2
      --ulysses-degree 2
      --encoder-parallel auto
      --performance-mode speed
    )
    ;;
  h200x4)
    h3_args=(
      --num-gpus 4
      --ulysses-degree 4
      --encoder-parallel auto
      --performance-mode speed
    )
    ;;
  rtx5090x2)
    h3_args=(
      --num-gpus 2
      --tp-size 2
      --ulysses-degree 1
      --encoder-parallel auto
      --performance-mode memory
      --layerwise-offload-components dit,text_encoder,vae
      --dit-offload-prefetch-size 1
      --dit-layerwise-resident-layers 20
      --enable-torch-compile false
    )
    ;;
  rtx4090x1)
    h3_args=(
      --quantization kitchen_int8
      --attention-backend fa
      --performance-mode memory
      --layerwise-offload-components dit,text_encoder
      --dit-offload-prefetch-size 1
      --dit-layerwise-resident-layers 0
      --enable-torch-compile false
    )
    ;;
  *)
    echo "Unknown H3_PROFILE: $profile" >&2
    exit 2
    ;;
esac

sglang serve \
  --model-path MiniMaxAI/MiniMax-H3 \
  --model-variant fl2va \
  --host "${SGLANG_HOST:-127.0.0.1}" \
  --port "${SGLANG_PORT:-30010}" \
  "${h3_args[@]}" &
sglang_pid=$!

cleanup() {
  kill "$sglang_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec uvicorn app.main:app --host 0.0.0.0 --port "${API_PORT:-8000}"
