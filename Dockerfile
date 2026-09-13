FROM lmsysorg/sglang:latest

LABEL org.opencontainers.image.source="https://github.com/Mat-Cav/minimax-h3-runpod"

WORKDIR /app

# The SGLang image includes its source tree. The diffusion extra supplies the
# MiniMax-H3 runtime and platform-specific dependencies.
RUN python3 -m pip install --no-cache-dir --upgrade \
      -e "/sgl-workspace/sglang/python[diffusion]" \
      comfy-kitchen

COPY requirements-api.txt ./
RUN python3 -m pip install --no-cache-dir -r requirements-api.txt

COPY app ./app
COPY handler.py ./handler.py
COPY scripts/start.sh ./scripts/start.sh
RUN chmod +x ./scripts/start.sh

ENV HF_HOME=/workspace/huggingface \
    SGLANG_HOST=127.0.0.1 \
    SGLANG_PORT=30010 \
    H3_PROFILE=h100x4

CMD ["./scripts/start.sh"]
