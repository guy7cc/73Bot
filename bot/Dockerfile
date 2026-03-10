FROM python:3.12-slim

WORKDIR /app

# Install ffmpeg, git and voice libraries for PyNaCl/discord.py/opus support
RUN apt-get update && \
    apt-get install -y ffmpeg git libopus0 libsodium23 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "main.py"]
