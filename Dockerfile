FROM python:3.11-slim

# potrzebne narzędzia systemowe
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# kopiujemy zależności
COPY requirements.txt /app/

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# kopiujemy kod źródłowy
COPY . /app

# katalog na pliki/audio
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
