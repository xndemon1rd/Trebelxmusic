FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ffmpeg curl ca-certificates unzip patch \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://deno.land/install.sh | sh \
    && ln -sf /root/.deno/bin/deno /usr/local/bin/deno \
    && deno --version

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

# Build the BgUtils PO-token provider used by yt-dlp. The provider plugin alone
# is not enough; the token provider service must also be running.
RUN git clone --depth 1 --branch 2.0.0 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-ytdlp-pot-provider \
    && cd /opt/bgutil-ytdlp-pot-provider/server \
    && deno install --allow-scripts=npm:canvas --frozen

COPY . .
RUN find . -type d -name __pycache__ -prune -exec rm -rf {} + \
    && find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete \
    && mkdir -p downloads cache couples TrabelxMusicBackup

CMD ["bash", "start"]
