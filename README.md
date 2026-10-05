# Vi Vu Đà Nẵng — Messenger Chatbot

AI-assisted Facebook Messenger chatbot for a vehicle rental service in Đà Nẵng.

**Tech:** FastAPI · PostgreSQL · Gemini AI · Meta Messenger API

## Features

- FAQ and command handling
- Vehicle availability checks
- Multi-step booking flow
- Gemini AI fallback
- Conversation history stored in PostgreSQL
- Facebook Messenger webhook integration

## Architecture

```text
Messenger
   ↓
Meta Webhook
   ↓
Message Router
   ├─ Commands
   ├─ FAQ Matching
   └─ Gemini AI
   ↓
Response Formatter
   ↓
Messenger + PostgreSQL
```

## Tech Stack

- **Backend:** FastAPI, Python
- **Database:** PostgreSQL, SQLAlchemy
- **AI:** Gemini API
- **Messaging:** Meta Messenger API
- **Testing:** Pytest
- **DevOps:** Docker, Docker Compose

## Quick Start

```bash
cp .env.example .env
docker-compose up -d
```

Required environment variables:

```env
META_VERIFY_TOKEN=
META_PAGE_ACCESS_TOKEN=
GEMINI_API_KEY=
```

Run tests:

```bash
pytest tests/ -v
```

## Main Project Structure

```text
app/
├── main.py
├── handlers/
│   ├── webhook.py
│   ├── rule_based.py
│   ├── availability.py
│   ├── booking.py
│   ├── ai.py
│   └── router.py
├── db/
└── ai/

migrations/
tests/
docker-compose.yml
Dockerfile
```

## Status

Currently in development.

Main implemented areas:
- Messenger webhook
- FAQ / command routing
- Gemini fallback
- Booking and availability logic
- PostgreSQL storage
- Automated tests

## License

MIT
