FROM nvidia/cuda:12.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV QWEN_MODEL=Qwen/Qwen2-VL-2B-Instruct

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    shared-mime-info \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    openjdk-17-jre-headless \
    wget \
    curl \
    unrar \
    p7zip-full \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://github.com/plantuml/plantuml/releases/download/v1.2024.0/plantuml-1.2024.0.jar \
    -O /opt/plantuml.jar

ENV PLANTUML_JAR=/opt/plantuml.jar

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY main.py evaluate.py extract.py ./

RUN ln -sf /opt/plantuml.jar /app/plantuml.jar

RUN mkdir -p /app/data /app/eval_output

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
