# Alpha-Commerce — FastAPI E-Commerce Backend

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.135-009688?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql" />
  <img src="https://img.shields.io/badge/Redis-Alpine-DC382D?style=for-the-badge&logo=redis" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker" />
</p>

A production-grade, async FastAPI backend for e-commerce — featuring a secure multi-layer JWT auth system, full cart and order lifecycle, address management, Razorpay payment infrastructure, and a Docker-first local setup.

---

## Table of Contents

- [Feature Overview](#feature-overview)
- [Architecture & Project Structure](#architecture--project-structure)
- [Authentication System — Deep Dive](#authentication-system--deep-dive)
- [API Endpoints Reference](#api-endpoints-reference)
- [Data Models](#data-models)
- [Local Setup (Docker)](#local-setup-docker)
- [Environment Variables](#environment-variables)
- [Tech Stack](#tech-stack)
- [Roadmap](#roadmap)

---

## Feature Overview

### 🔐 Authentication & Security
- JWT **access + refresh token** dual-token flow
- **Refresh token rotation** — every `/refresh` call issues a new pair and blacklists the old refresh token
- **Redis-backed token blacklist** — instant token revocation on logout and password reset
- **Token theft detection** — blacklisted refresh tokens trigger a `401` with a compromise alert
- **Dual-layer login rate limiting** — throttles both by IP *and* by username to block distributed brute-force
- **Session invalidation on password reset** — `password_changed_at` timestamp invalidates all tokens issued before the reset
- **UUID-based token subjects** — tokens carry `user.id` (UUID) instead of username for performance and privacy
- **Argon2 password hashing** with automatic hash upgrade on login (`verify_and_update`)
- **Email verification flow** — registration creates inactive accounts; a background-task email activates them
- **Verification email cooldown** — 2-minute Redis-backed cooldown on resend requests to prevent abuse
- **Single-use password reset tokens** — tokens are blacklisted immediately after use; cannot be replayed
- **Admin & role-based access control** — `require_roles()` dependency supports multi-role guards (e.g., `admin`, `manager`)
- **Token type enforcement** — `access`, `refresh`, `email_verification`, and `password_reset` tokens are structurally distinct and validated on every request

### 🛍️ Catalog
- Category management with **self-referential parent/child hierarchy** (slug-indexed)
- Product CRUD with **soft delete** — deleted products are hidden from listings but retained for order history integrity
- JSONB `attributes` field for flexible, schema-less product metadata
- Pagination support on product listings

### 🛒 Cart
- Auto-created cart on first access — no explicit cart creation required
- **Ghost product cleanup** — soft-deleted or hard-deleted products are silently removed from carts on fetch
- Real-time **stock validation** on add and update operations
- **Quantity decrement** shortcut — decrements by 1, removes item automatically at zero
- ORM-level `total_price` property calculated directly from relationships
- `UniqueConstraint` on `(cart_id, product_id)` — duplicate add merges quantities instead of creating duplicates

### 📦 Orders & Checkout
- **Cart → Order conversion** in a single atomic transaction
- **18% GST** applied to subtotal; ₹50 flat shipping fee waived on orders above ₹500
- **Atomic stock decrement** — concurrent over-purchase is blocked at DB level
- `price_at_purchase` snapshot on each `OrderItem` — historical accuracy even after price changes
- **Address snapshot** saved on order — correct shipping record even after user deletes the address
- Order history and per-order detail retrieval (user-scoped)
- `OrderStatus` enum: `pending → paid → processing → shipped → delivered → cancelled`

### 📍 Address Book
- Full CRUD with **soft delete** — addresses used in past orders are never hard-deleted
- **Auto-default** — first address added is automatically set as default
- **Atomic default switching** — race condition safe; only one address can be default at a time
- User-scoped queries — users cannot access or modify each other's addresses

### 💳 Payment Infrastructure (Razorpay)
- `Transaction` model ready with `razorpay_order_id`, `razorpay_payment_id`, and `razorpay_signature` fields
- Status tracking: `PENDING` → success/failure
- Schema designed for Razorpay webhook-based payment confirmation

### ⚙️ Developer Experience
- **Modular model architecture** — models split into `user`, `product`, `cart`, `order`, `address`, `transaction`
- **Service layer pattern** — business logic in `app/services/`, routes stay thin
- **Async SQLAlchemy** with `asyncpg` driver throughout
- **Alembic** migration support for modular schema evolution
- **System-wide structured logging** via `logging_config.py`
- **Celery** worker infrastructure scaffolded (`app/worker/celery_app.py`) for async task support
- **Schemathesis** + **pytest** in dependencies for API contract testing

---

## Architecture & Project Structure

```text
E-Commerce/
├── alembic/                        # Database migration scripts
│   ├── versions/
│   ├── env.py
│   └── archived/
├── app/
│   ├── api/
│   │   ├── dependencies.py         # get_current_user, require_roles, auth guards
│   │   └── v1/
│   │       ├── auth.py             # All auth endpoints
│   │       ├── products.py         # Catalog & category endpoints
│   │       ├── cart.py             # Cart management endpoints
│   │       └── order.py            # Checkout & order history endpoints
│   ├── core/
│   │   ├── config.py               # Pydantic settings (env-driven)
│   │   ├── redis.py                # Redis client + rate limiting logic
│   │   ├── security.py             # JWT creation, blacklist, Argon2 hashing
│   │   └── logging_config.py       # Structured logging setup
│   ├── db/
│   │   ├── models/
│   │   │   ├── user.py             # User, email/username validators
│   │   │   ├── product.py          # Product, Category (self-referential)
│   │   │   ├── cart.py             # Cart, CartItem
│   │   │   ├── order.py            # Order, OrderItem, OrderStatus enum
│   │   │   ├── address.py          # Address (soft delete + default logic)
│   │   │   └── transaction.py      # Razorpay Transaction
│   │   ├── base.py                 # SQLAlchemy declarative Base
│   │   ├── base_class.py
│   │   └── session.py              # Async session factory + get_db
│   ├── schemas/
│   │   ├── user.py
│   │   ├── product.py
│   │   ├── cart.py
│   │   ├── order.py
│   │   └── address.py
│   ├── services/
│   │   ├── cart_service.py         # CartService class (full cart lifecycle)
│   │   ├── order_service.py        # checkout_user_cart, get_user_orders
│   │   ├── product_service.py      # ProductService (CRUD + soft delete)
│   │   ├── category_service.py     # CatalogService
│   │   ├── address_service.py      # AddressService (default, soft delete)
│   │   └── utils.py
│   ├── utils/
│   │   └── email.py                # FastAPI-Mail background email sender
│   ├── worker/
│   │   └── celery_app.py           # Celery app instance
│   └── main.py                     # FastAPI app, router registration
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── alembic.ini
```

---

## Authentication System — Deep Dive

This section documents the full auth flow as implemented in `auth.py`, `dependencies.py`, and `security.py`.

### Registration & Email Verification

```
POST /auth/register
  → Validates email uniqueness (case-insensitive)
  → Hashes password with Argon2
  → Creates User with is_active=False
  → Dispatches verification email via BackgroundTask
  → Returns UserOut (no token issued yet)

GET /auth/verify?token=<token>
  → Decodes JWT, validates type == "email_verification"
  → Sets user.is_active = True
  → Blacklists verification token (single-use)

POST /auth/resend-verification
  → Generic response to prevent email enumeration
  → 2-minute Redis cooldown per email (key: email_cooldown:<email>)
```

### Login & Token Issuance

```
POST /auth/login  (OAuth2PasswordRequestForm)
  → Rate limit check #1: IP-based   (5 attempts / 60s)
  → Rate limit check #2: Username-based  (5 attempts / 60s) ← blocks proxy-distributed attacks
  → Fetches user by email (case-insensitive)
  → Verifies password with Argon2 verify_and_update (re-hashes if algo is outdated)
  → Blocks login if is_active == False (403)
  → Issues access_token (sub=user.id UUID, type=access, jti=uuid4)
  → Issues refresh_token (sub=user.id UUID, type=refresh, jti=uuid4, exp=7d)
```

### Token Validation on Protected Routes (`get_current_user`)

Every protected route runs through this dependency chain:

```
1. Redis blacklist check — rejects revoked tokens instantly
2. JWT decode + claims validation:
     - type must be "access"
     - sub must be a valid UUID
     - exp must be in the future
3. User lookup by UUID (optimized — no username index scan)
4. Session invalidation check:
     - token.iat < user.password_changed_at → reject (forces re-login after password reset)
5. is_active check — rejects unverified or disabled accounts
```

### Token Refresh & Rotation

```
POST /auth/refresh
  → Validates type == "refresh"
  → Checks blacklist — blacklisted refresh token triggers 401 "Token compromised"
  → Blacklists old refresh token (TTL-aware)
  → Issues new access_token + new refresh_token (rotation)
```

### Logout

```
POST /auth/logout
  → Computes remaining TTL of the access token
  → Adds token to Redis blacklist with exact TTL
  → Token is now invalid for all future requests
```

### Password Reset

```
POST /auth/forgot-password
  → Generic response regardless of email existence (no enumeration)
  → Generates password_reset token (type=password_reset, exp=15min) — currently simulated

POST /auth/reset-password
  → Blacklist check — rejects already-used tokens
  → Validates type == "password_reset" and email match
  → Updates hashed_password with Argon2
  → Sets user.password_changed_at = now() ← invalidates ALL existing sessions
  → Blacklists the reset token (single-use enforcement)
```

### Role-Based Access Control

```python
# Usage in routes:
Depends(require_roles("admin"))           # Admin only
Depends(require_roles("admin", "manager")) # Admin OR Manager
```

The `require_roles()` factory returns a FastAPI dependency that calls `get_current_active_user` internally, then checks the user's role set against the required roles.

---

## API Endpoints Reference

### Authentication — `/auth`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/register` | Public | Register new user, sends verification email |
| `POST` | `/auth/resend-verification` | Public | Resend verification email (2 min cooldown) |
| `GET` | `/auth/verify` | Public | Activate account via email token |
| `POST` | `/auth/login` | Public | Login, returns access + refresh tokens |
| `POST` | `/auth/refresh` | Public | Rotate refresh token, get new pair |
| `POST` | `/auth/logout` | Bearer | Blacklist current access token |
| `POST` | `/auth/forgot-password` | Public | Trigger password reset (generic response) |
| `POST` | `/auth/reset-password` | Public | Reset password with token |
| `POST` | `/auth/admin-only` | Admin | Admin-only action endpoint |
| `GET` | `/auth/admin-dashboard` | Admin | Admin dashboard |
| `GET` | `/auth/inventory` | Admin / Manager | Inventory view |

### Catalog — `/api/v1/products`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/products/categories` | Public | Create a category |
| `GET` | `/api/v1/products/categories` | Public | List all categories |
| `POST` | `/api/v1/products/` | Public | Create a product |
| `GET` | `/api/v1/products/` | Public | List products (paginated) |
| `GET` | `/api/v1/products/{product_id}` | Public | Get product by ID |
| `DELETE` | `/api/v1/products/{product_id}` | Public | Soft-delete a product |

### Cart — `/api/v1/cart`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/cart/` | Bearer | Get current user's cart |
| `POST` | `/api/v1/cart/items` | Bearer | Add item to cart |
| `PUT` | `/api/v1/cart/items/{item_id}` | Bearer | Update item quantity |
| `PATCH` | `/api/v1/cart/items/{item_id}/decrease` | Bearer | Decrease quantity by 1 |
| `DELETE` | `/api/v1/cart/items/{item_id}` | Bearer | Remove specific item |
| `DELETE` | `/api/v1/cart/` | Bearer | Clear entire cart |

### Orders — `/api/v1/orders`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/orders/checkout` | Bearer | Convert cart to order (atomic) |
| `GET` | `/api/v1/orders/` | Bearer | List user's order history |
| `GET` | `/api/v1/orders/{order_id}` | Bearer | Get specific order details |

---

## Data Models

### User
| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `username` | String(50) | Unique, min 3 chars |
| `email` | String(100) | Unique, lowercased, validated |
| `hashed_password` | String | Argon2 hash |
| `password_changed_at` | DateTime (tz) | Used for session invalidation |
| `is_active` | Boolean | False until email verified |
| `is_admin` | Boolean | Role flag |
| `is_deleted` | Boolean | Soft delete |
| `phone_number` | String(20) | Optional, for Razorpay |
| `full_name` | String(100) | Optional |

### Product & Category
- `Category` supports self-referential parent/child hierarchy via `parent_id`
- `Product` has JSONB `attributes` for flexible metadata
- Both support soft delete via `is_deleted`

### Cart & CartItem
- `Cart` is user-scoped, auto-created on first access
- `CartItem` has a `UniqueConstraint(cart_id, product_id)` — no duplicate entries
- `Cart.total_price` is an ORM-level `@property`

### Order & OrderItem
- Stores `subtotal_price`, `tax_price`, `shipping_price`, `total_price` separately
- `OrderItem.price_at_purchase` freezes the price at time of checkout
- `shipping_address_snapshot` stores a text copy of the address

### Transaction
- Linked to `Order` via `order_id`
- Stores `razorpay_order_id`, `razorpay_payment_id`, `razorpay_signature`
- Status: `PENDING` → `SUCCESS` / `FAILED`

---

## Local Setup (Docker)

### 1. Clone the repository
```bash
git clone https://github.com/Vishwam401/E-commerce.git
cd E-commerce
```

### 2. Create the environment file
Create `.env.docker` in the project root:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:vish@db:5432/ecommerce_db

# JWT
SECRET_KEY=your_super_secret_key_min_32_chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis (must match docker-compose redis command)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Email (Gmail SMTP example)
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_FROM=your_email@gmail.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_STARTTLS=True
MAIL_SSL_TLS=False

# For LAN/mobile testing, replace with your machine's local IP
EMAIL_VERIFY_BASE_URL=http://192.168.x.x:8001
```

### 3. Start all services
```bash
docker compose up --build -d
```

This starts three containers: `ecommerce_api_cont`, `ecommerce_db_cont`, `ecommerce_redis`.

### 4. Run database migrations
```bash
docker compose exec api alembic upgrade head
```

### 5. Access the API
| Interface | URL |
|-----------|-----|
| API Root | `http://localhost:8001` |
| Swagger UI | `http://localhost:8001/docs` |
| ReDoc | `http://localhost:8001/redoc` |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | PostgreSQL async connection string |
| `SECRET_KEY` | ✅ | — | JWT signing key (min 32 chars recommended) |
| `ALGORITHM` | ✅ | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | `30` | Access token lifetime |
| `REDIS_HOST` | ✅ | — | Redis hostname |
| `REDIS_PORT` | ✅ | `6379` | Redis port |
| `REDIS_PASSWORD` | ✅ | — | Redis auth password |
| `MAIL_USERNAME` | ✅ | — | SMTP username |
| `MAIL_PASSWORD` | ✅ | — | SMTP password / app password |
| `MAIL_FROM` | ✅ | — | Sender email address |
| `MAIL_PORT` | ✅ | `587` | SMTP port |
| `MAIL_SERVER` | ✅ | — | SMTP server hostname |
| `MAIL_STARTTLS` | ✅ | `True` | Enable STARTTLS |
| `MAIL_SSL_TLS` | ✅ | `False` | Enable SSL/TLS |
| `EMAIL_VERIFY_BASE_URL` | ✅ | `http://localhost:8001` | Base URL for email verification links |

---

## Quick Verification Checklist

Test the full auth lifecycle after setup:

1. **Register** — `POST /auth/register` with a valid email
2. **Verify email** — Open the link from your inbox (`GET /auth/verify?token=...`)
3. **Login** — `POST /auth/login`, save the `access_token` and `refresh_token`
4. **Access protected route** — `GET /api/v1/cart/` with Bearer token
5. **Trigger rate limit** — Send 6+ wrong-password login attempts, expect `429`
6. **Wait 60s** — Confirm login works again
7. **Logout** — `POST /auth/logout`, then confirm old token returns `401`
8. **Refresh token** — `POST /auth/refresh`, confirm new token pair is returned
9. **Password reset** — `POST /auth/reset-password`, confirm old tokens are invalidated

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.135 |
| Language | Python 3.11+ |
| Database | PostgreSQL 15 (asyncpg driver) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Cache / Blacklist | Redis (Authenticated, Alpine) |
| Password Hashing | Argon2 (via passlib) |
| JWT | python-jose |
| Email | FastAPI-Mail / SMTP |
| Task Queue | Celery (scaffolded) |
| Containerization | Docker / Docker Compose |
| Validation | Pydantic v2 |
| Testing | pytest, Schemathesis |

---

## Roadmap

- [x] JWT Authentication with email verification
- [x] Redis-backed token blacklist & rate limiting
- [x] Modular model architecture
- [x] Catalog (Products + Categories)
- [x] Full Cart lifecycle
- [x] Order & Checkout with atomic stock management
- [x] Address Book with soft delete
- [x] Razorpay Transaction model
- [ ] Razorpay payment integration & webhook handler
- [ ] Redis-backed cart caching
- [ ] Coupon & discount engine
- [ ] Order status update flow (admin)
- [ ] Celery async tasks (email, order processing)
- [ ] Sentry error tracking integration

---

## Contributing

Contributions, issues, and feature requests are welcome. Check the [issues page](https://github.com/Vishwam401/E-commerce/issues) to get started.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/Vishwam401">Vishwam401</a>
</p>
