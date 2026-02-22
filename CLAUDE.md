# weibo Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-22

## Active Technologies
- Python 3.13 (기존 프로젝트와 동일) + requests, python-telegram-bot[job-queue], Pillow, anthropic, python-dotenv (기존 그대로) (002-weibo-cookie-posting)
- JSON 파일 (`data/weibo_cookies.json`, 기존 `data/posts/`, `data/history/`) (002-weibo-cookie-posting)
- Python 3.13 (Raspberry Pi 기존 설치) + python-telegram-bot[job-queue], requests, Pillow, anthropic, python-dotenv, flask (신규 - 내부 API) (003-openclaw-marketing-auto)
- JSON 파일 (data/ 디렉토리, 기존 패턴 유지) (003-openclaw-marketing-auto)

- Python 3.13 (Raspberry Pi 기존 설치) + python-telegram-bot v21.x, requests, Pillow, anthropic (Claude API) (001-weibo-auto-posting)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.13 (Raspberry Pi 기존 설치): Follow standard conventions

## Recent Changes
- 003-openclaw-marketing-auto: Added Python 3.13 (Raspberry Pi 기존 설치) + python-telegram-bot[job-queue], requests, Pillow, anthropic, python-dotenv, flask (신규 - 내부 API)
- 002-weibo-cookie-posting: Added Python 3.13 (기존 프로젝트와 동일) + requests, python-telegram-bot[job-queue], Pillow, anthropic, python-dotenv (기존 그대로)

- 001-weibo-auto-posting: Added Python 3.13 (Raspberry Pi 기존 설치) + python-telegram-bot v21.x, requests, Pillow, anthropic (Claude API)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
