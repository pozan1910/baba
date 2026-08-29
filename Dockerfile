FROM python:3.10-slim

# FFmpeg ve gerekli sistem araçlarını yükle
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bağımlılıkları yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Botu başlat
CMD ["python", "bot.py"]