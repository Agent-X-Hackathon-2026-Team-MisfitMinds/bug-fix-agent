FROM python:3.12-slim

RUN useradd --create-home --uid 10001 nonroot && mkdir -p /workspace \
    && chown nonroot:nonroot /workspace

WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir pytest==8.3.4

USER nonroot
CMD ["python", "-m", "pytest", "-q"]
