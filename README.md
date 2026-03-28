# 🛒 MyEcommerceApp — Backend

FastAPI · PostgreSQL · Redis · Celery · Docker · WebSocket · JWT Auth

---

## 🏗️ Architecture

```
┌──────────────┐     HTTP/WS     ┌──────────────────────────┐
│   Frontend   │ ─────────────▶ │   FastAPI (port 8000)    │
└──────────────┘                 └───────┬──────────────────┘
                                         │
              ┌──────────────────────────┼────────────────────┐
              ▼                          ▼                    ▼
     ┌─────────────────┐      ┌──────────────────┐   ┌──────────────┐
     │  PostgreSQL :5432│      │   Redis  :6379   │   │  Celery      │
     │  (persistent DB) │      │  cache/pubsub/   │   │  Worker      │
     └─────────────────┘      │  task broker     │   └──────────────┘
                               └──────────────────┘
```

## 📁 Project Structure

```
app/
├── api/
│   ├── deps.py              # FastAPI dependencies (auth, db, redis)
│   └── v1/
│       ├── router.py        # Mounts all sub-routers
│       └── endpoints/
│           ├── auth.py      # POST /auth/login, /auth/refresh
│           ├── users.py     # CRUD /users/
│           ├── files.py     # POST /files/upload, GET /files/{id}
│           ├── websocket.py # WS  /ws/{room_id}, /ws/notify/{user_id}
│           └── health.py    # GET /health
├── core/
│   ├── config.py            # Pydantic settings (reads .env)
│   ├── security.py          # JWT encode/decode, password hashing
│   └── logging.py           # Structured logging setup
├── db/
│   ├── base.py              # SQLAlchemy DeclarativeBase
│   ├── session.py           # Async engine + get_db() dependency
│   └── redis.py             # Redis pool + get_redis() dependency
├── models/
│   ├── user.py              # User ORM model
│   └── order.py             # Order + OrderItem ORM models
├── schemas/
│   └── user.py              # Pydantic v2 schemas (request/response)
├── services/
│   └── user_service.py      # Business logic layer
├── tasks/
│   ├── celery_app.py        # Celery application instance
│   └── example_tasks.py     # send_email_task, process_data_task
└── main.py                  # FastAPI app factory + lifespan
alembic/                     # DB migrations
tests/                       # pytest suite
```

---

## 🚀 Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/your-org/your-repo.git
cd your-repo
cp .env.example .env
# Edit .env — set SECRET_KEY, passwords, etc.
```

Generate a secure `SECRET_KEY`:
```bash
openssl rand -hex 32
```

### 2. Start all services

```bash
make up
```

| Service   | URL                                        |
|-----------|--------------------------------------------|
| API docs  | http://localhost:8000/api/v1/docs          |
| ReDoc     | http://localhost:8000/api/v1/redoc         |
| Health    | http://localhost:8000/api/v1/health        |
| Flower    | http://localhost:5555                      |
| Adminer   | http://localhost:8080 (dev profile only)   |

Start Adminer (DB UI):
```bash
docker compose --profile dev up -d
```

### 3. Run migrations

```bash
make migrate
```

---

## 🔑 Authentication Flow

```
POST /api/v1/auth/login        → { access_token, refresh_token }
GET  /api/v1/auth/me           → current user (Bearer token required)
POST /api/v1/auth/refresh      → new token pair
POST /api/v1/auth/logout       → stateless logout
```

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

---

## 📡 WebSocket

**Room chat / broadcast:**
```
ws://localhost:8000/api/v1/ws/{room_id}?token=<JWT>
```

**Personal notifications:**
```
ws://localhost:8000/api/v1/ws/notify/{user_id}?token=<JWT>
```

Push a notification from backend:
```python
import redis, json
r = redis.from_url("redis://localhost:6379")
r.publish(f"ws:user:{user_id}", json.dumps({"type": "order_update", "order_id": "..."}))
```

---

## 📦 File Upload

```bash
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@photo.jpg"
```

Allowed types: `image/jpeg`, `image/png`, `image/webp`, `image/gif`, `application/pdf`, `text/csv`
Max size: **10 MB**

---

## ⚙️ Background Tasks (Celery)

Dispatch from anywhere in the app:

```python
from app.tasks.example_tasks import send_email_task

# Fire-and-forget
send_email_task.delay(to="user@example.com", subject="Welcome!", body="...")

# Get result
result = send_email_task.apply_async(args=[...])
print(result.get(timeout=10))
```

Add a periodic task in `celery_app.py`:
```python
celery_app.conf.beat_schedule = {
    "cleanup-every-night": {
        "task": "tasks.process_data",
        "schedule": crontab(hour=2, minute=0),
        "args": [{"type": "nightly_cleanup"}],
    },
}
```

---

## 🧪 Tests

```bash
make test                    # inside Docker
# or locally:
pytest tests/ -v --cov=app
```

---

## 🛠️ Common Commands

```bash
make up                      # start services
make down                    # stop services
make logs                    # tail API logs
make shell                   # bash in API container
make migrate                 # run alembic upgrade head
make migrate-create MSG="add products table"
make test
make lint
make format
```

---

## 🚢 Production Checklist

- [ ] Set strong `SECRET_KEY` in `.env`
- [ ] Set `DEBUG=false` and `ENVIRONMENT=production`
- [ ] Set `POSTGRES_PASSWORD` to a strong random password
- [ ] Switch `uvicorn` workers to `gunicorn -k uvicorn.workers.UvicornWorker`
- [ ] Add HTTPS termination (nginx / Traefik)
- [ ] Move file uploads to S3 / GCS (replace `files.py` storage backend)
- [ ] Add token blacklist in Redis for proper logout
- [ ] Set up log aggregation (Loki / CloudWatch)
- [ ] Configure `ALLOWED_ORIGINS` to your domain only
