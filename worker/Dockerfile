# Card Studio geometry worker.
#
# Build from the repository root, because the image needs build_card.py:
#     docker build -f worker/Dockerfile -t card-worker .
#
# The fonts are the reason this is a container and not a serverless function.
# build_card draws real glyph outlines, so what it produces depends on which
# faces are installed. Pinning DejaVu here is what makes a card come out the
# same in production as it does in CI.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY worker/requirements.txt ./worker/requirements.txt
RUN pip install --no-cache-dir -r worker/requirements.txt

COPY build_card.py ./build_card.py
COPY worker/ ./worker/

RUN adduser --disabled-password --gecos "" --uid 10001 app \
    && chown -R app:app /app
USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status==200 else 1)"

CMD ["uvicorn", "worker.app:app", "--host", "0.0.0.0", "--port", "8080", \
     "--workers", "1", "--timeout-keep-alive", "30"]
