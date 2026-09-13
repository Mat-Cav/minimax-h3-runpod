#!/usr/bin/env bash
set -Eeuo pipefail

mkdir -p "${HF_HOME:-/workspace/huggingface}"

model_path="${MODEL_PATH:-MiniMaxAI/MiniMax-H3}"
cached_root="/runpod-volume/huggingface-cache/hub/models--MiniMaxAI--MiniMax-H3"
if [[ -f "$cached_root/refs/main" ]]; then
  cached_revision="$(tr -d '\n' < "$cached_root/refs/main")"
  cached_snapshot="$cached_root/snapshots/$cached_revision"
  if [[ -d "$cached_snapshot" ]]; then
    model_path="$cached_snapshot"
  fi
fi

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
  --model-path "$model_path" \
  --model-variant fl2va \
  --host "${SGLANG_HOST:-127.0.0.1}" \
  --port "${SGLANG_PORT:-30010}" \
  "${h3_args[@]}" &
sglang_pid=$!

cleanup() {
  kill "$sglang_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec python3 handler.py
