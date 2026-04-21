# Alpha-Commerce Backend

A FastAPI-based E-commerce backend with JWT authentication, Redis-backed token revocation, PostgreSQL persistence, and Docker-first local development.

## Current Features

### Authentication & Security
- JWT access + refresh token flow
- Redis-backed token blacklist on logout
- Redis-backed login rate limiting (IP based, `5` attempts per `60s`)
- Access-token type validation for protected routes
- Admin-only route protection using role dependency (`is_admin`)
- Email verification flow:
  - Register creates user in inactive state (`is_active=False`)
  - Verification token generated and sent via background email task
  - `GET /auth/verify` activates account
  - Login blocked for unverified users (`403`)
- Password reset flow:
  - `forgot-password` keeps response generic (no email enumeration)
  - `reset-password` validates token type + email match + strong password

### Developer Experience
- Docker Compose setup for API + PostgreSQL + Redis
- SQLAlchemy async session setup
- Alembic migration support
- Pydantic schema validation with strong password rules
- Config-driven email verification URL (`EMAIL_VERIFY_BASE_URL`) for mobile/LAN testing

## Project Structure

```text
E-Commerce/
├── alembic/
├── app/
│   ├── api/
│   │   ├── dependencies.py
│   │   └── v1/auth.py
│   ├── core/
│   │   ├── config.py
│   │   ├── redis.py
│   │   └── security.py
│   ├── db/
│   ├── schemas/
│   ├── utils/
│   │   └── email.py
│   └── main.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── alembic.ini
```

## Tech Stack
- FastAPI
- PostgreSQL
- Redis
- SQLAlchemy
- Alembic
- FastAPI-Mail / SMTP (email verification)
- Docker / Docker Compose

## Local Setup (Docker)

### 1) Clone
```bash
git clone https://github.com/Vishwam401/E-commerce.git
cd E-commerce
```

### 2) Environment file
Create `.env.docker`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:vish@db:5432/ecommerce_db
SECRET_KEY=your_super_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDIS_HOST=redis
REDIS_PORT=6379

MAIL_USERNAME=your_email@example.com
MAIL_PASSWORD=your_app_password
MAIL_FROM=your_email@example.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_STARTTLS=True
MAIL_SSL_TLS=False

# Use a phone/LAN reachable URL in local network testing
EMAIL_VERIFY_BASE_URL=http://YOUR_LAN_IP:8001
```

### 3) Start services
```bash
docker compose up --build -d
```

### 4) Run migrations
```bash
docker compose exec api alembic upgrade head
```

### 5) Access API
- API: `http://localhost:8001`
- Swagger: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## Auth Endpoints (Current)
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/verify`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/admin-only`
- `GET /auth/admin-dashboard`
- `GET /auth/inventory`

## Quick Verification Checklist
1. Register with a new email (`POST /auth/register`)
2. Open verification link from email (`GET /auth/verify?token=...`)
3. Login with verified account (`POST /auth/login`)
4. Trigger rate limit using repeated wrong-password attempts and confirm `429`
5. Wait 60 seconds and confirm login attempts are allowed again

## Roadmap (Planned)
- Product/catalog modules
- Cart and order lifecycle
- Coupon/discount engine
- Webhooks and payment integrations
- Search and filtering enhancements

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
Feel free to check the [issues page](https://github.com/Vishwam401/E-commerce/issues).

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/Vishwam401">Vishwam401</a>
</p>
