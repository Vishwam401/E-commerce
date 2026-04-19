# Alpha-Commerce Backend

A FastAPI-based E-commerce backend with JWT authentication, Redis-backed token revocation, PostgreSQL persistence, and Docker-first local development.

## Current Features

### Authentication & Security
- JWT access + refresh token flow
- Redis-backed token blacklist on logout
- Access-token type validation for protected routes
- Admin-only route protection using role dependency (`is_admin`)
- Password reset flow:
  - `forgot-password` generates a simulated reset token
  - `reset-password` validates token type + email match + strong password

### Developer Experience
- Docker Compose setup for API + PostgreSQL + Redis
- SQLAlchemy async session setup
- Alembic migration support
- Pydantic schema validation with strong password rules

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
│   │   └── security.py
│   ├── db/
│   ├── schemas/
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
- Docker / Docker Compose

## Local Setup (Docker)

### 1) Clone
```bash
git clone https://github.com/Vishwam401/E-commerce.git
cd E-commerce
```

### 2) Environment file
Create `.env.docker` (or use the existing project convention):

```env
DATABASE_URL=postgresql+asyncpg://postgres:vish@db:5432/ecommerce_db
SECRET_KEY=your_super_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDIS_HOST=redis
REDIS_PORT=6379
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
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/admin-only`

## Roadmap (Planned)
- Product/catalog modules
- Cart and order lifecycle
- Coupon/discount engine
- Webhooks and payment integrations
- Advanced security middleware (rate limiting, headers)
- Search and filtering enhancements

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! 
Feel free to check the [issues page](https://github.com/Vishwam401/E-commerce/issues).

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/Vishwam401">Vishwam401</a>
</p>
