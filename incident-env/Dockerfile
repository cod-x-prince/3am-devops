FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu" \
    PATH="/root/.cargo/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    pkg-config \
    libssl-dev \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --profile minimal --default-toolchain stable

WORKDIR /app

COPY pyproject.toml README.md openenv.yaml inference.py tasks.py ./
COPY engine ./engine
COPY api ./api
COPY envs ./envs
COPY training ./training
COPY rewards ./rewards
COPY graders ./graders
COPY scenarios ./scenarios
COPY tests ./tests
COPY dashboard ./dashboard
COPY Makefile ./

RUN python -m pip install --upgrade pip \
 && pip install --index-url https://download.pytorch.org/whl/cpu torch \
 && pip install -e .

EXPOSE 7860

CMD ["sh", "-lc", "python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
