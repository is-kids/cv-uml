FROM nvidia/cuda:12.1-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    shared-mime-info \
    tesseract-ocr \
    tesseract-ocr-rus \
    openjdk-17-jre-headless \
    wget \
    unrar \
    p7zip-full \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://github.com/plantuml/plantuml/releases/download/v1.2024.0/plantuml-1.2024.0.jar \
    -O /opt/plantuml.jar

ENV PLANTUML_JAR=/opt/plantuml.jar

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY main.py batch_process.py ./

RUN ln -sf /opt/plantuml.jar /app/plantuml.jar

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
