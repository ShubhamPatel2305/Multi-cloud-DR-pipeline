FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user -r requirements.txt


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/app/.local/bin:$PATH

RUN groupadd -g 10001 app && useradd -u 10001 -g app -m app

COPY --from=builder /root/.local /home/app/.local
RUN chown -R app:app /home/app/.local

WORKDIR /srv
COPY --chown=app:app src ./src

USER app

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health/live',timeout=2).status==200 else 1)"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
