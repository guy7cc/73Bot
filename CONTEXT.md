# 73Bot Project Context

## 1. 目的 (Objective)
従来の「SimpleTTSBot」を刷新し、Dockerを利用してWindows/Linux間での完全なポータビリティを実現したDiscord読み上げBOTのバックエンドを開発する。

## 2. 技術スタック (Tech Stack)
* **言語**: Python 3.13+
* **API Framework**: FastAPI (音声生成・管理用)
* **Bot Framework**: discord.py (または disnake) ※本プロジェクトでは discord.py を採用
* **インフラ**: Docker / Docker Compose
* **音声合成エンジン**: COEIROINK v2 API (外部連携)
* **依存ツール**: FFmpeg (Dockerイメージ内に内蔵)

## 3. アーキテクチャ構成 (Architecture)
マイクロサービス設計を採用し、以下の2コンテナ構成とする：
* **`tts-backend`**: FastAPIで構築。テキストを受け取り、COEIROINK APIを叩いて音声バイナリを生成・返却する。将来的なエンジンの切り替えを容易にするための抽象レイヤー。
* **`discord-bot`**: Discordのボイスチャンネルを制御。メッセージを検知して `tts-backend` から音声を取得し、FFmpegでストリーミング再生する。

## 4. 開発要件 (Requirements)
* **ポータビリティ**: Windows (WSL2) および Linux環境で `docker compose up` だけで動作すること。
* **設定管理**: `env` ファイル（`.env`）によるトークンやAPI URLの管理。
* **ディレクトリ構造**:
```text
.
├── docker-compose.yml
├── backend/         # FastAPI source code
│   ├── Dockerfile
│   └── main.py
└── bot/             # Discord bot source code
    ├── Dockerfile
    └── main.py
```
