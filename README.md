# Alpha-Commerce — FastAPI E-Commerce Backend

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=28&pause=1000&color=009688&center=true&vCenter=true&width=600&lines=Alpha-Commerce+%F0%9F%9B%92;Production-Grade+FastAPI+Backend;Secure+%7C+Async+%7C+Payment-Ready" alt="Typing SVG" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.135-009688?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql" />
  <img src="https://img.shields.io/badge/Redis-Alpine-DC382D?style=for-the-badge&logo=redis" />
  <img src="https://img.shields.io/badge/Razorpay-Webhook-02042B?style=for-the-badge&logo=razorpay" />
  <img src="https://img.shields.io/badge/Celery-Active-37814A?style=for-the-badge&logo=celery" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker" />
  <img src="https://img.shields.io/badge/Coupons-Engine-FF6B35?style=for-the-badge&logo=ticket" />
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/Vishwam401/E-commerce?style=social" />
  <img src="https://img.shields.io/github/forks/Vishwam401/E-commerce?style=social" />
  <img src="https://img.shields.io/github/last-commit/Vishwam401/E-commerce?color=009688" />
</p>

> A production-grade, async FastAPI e-commerce backend featuring a secure multi-layer JWT auth system, full cart and order lifecycle, live Razorpay payment integration with a complete server-side webhook handler, Celery-powered async invoice emails, order cancellation with atomic stock rollback, a coupon & discount engine, a complete admin panel, user profile management, and a Docker-first local setup.

---

## Table of Contents

- [Feature Overview](#feature-overview)
- [Architecture & Project Structure](#architecture--project-structure)
- [Authentication System — Deep Dive](#authentication-system--deep-dive)
- [Razorpay Payment Flow](#razorpay-payment-flow)
- [Razorpay Webhook Handler](#razorpay-webhook-handler)
- [Celery Async Task — Invoice Email](#celery-async-task--invoice-email)
- [Order State Machine](#order-state-machine)
- [Coupon & Discount Engine](#coupon--discount-engine)
- [Admin Panel](#admin-panel)
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
- **Dual-layer login rate limiting** — throttles by both IP *and* username to block proxy-distributed brute-force attacks
- **Session invalidation on password reset** — `password_changed_at` timestamp invalidates all tokens issued before the reset
- **UUID-based token subjects** — tokens carry `user.id` (UUID) instead of username for performance and privacy
- **Argon2 password hashing** with automatic hash upgrade on login (`verify_and_update`)
- **Email verification flow** — registration creates inactive accounts; a background-task email activates them
- **Verification email cooldown** — 2-minute Redis-backed cooldown on resend requests to prevent spam
- **Single-use password reset tokens** — blacklisted immediately after use; cannot be replayed
- **Admin & role-based access control** — `require_roles()` dependency supports multi-role guards (e.g., `admin`, `manager`)
- **Token type enforcement** — `access`, `refresh`, `email_verification`, and `password_reset` tokens are structurally distinct and validated on every request

### 👤 User Profile Management
- `GET /api/v1/users/me` — fetch authenticated user's own profile
- `PATCH /api/v1/users/me` — partial profile update (name, email, phone)
- **Indian phone number validation** — auto-normalizes to `+91XXXXXXXXXX` format
- **Row-level lock** on email update — race condition safe (`SELECT ... FOR UPDATE`)
- **Email uniqueness re-check** on update — prevents stealing another user's email
- `GET /api/v1/users/me/orders` — paginated personal order history with limit/offset

### 🛡️ Admin Panel
- **Full product management** — create, list (all incl. soft-deleted), partial update, soft-delete
- **Platform-wide order management** — list all orders with optional `status` filter, paginated
- **Order status transitions** — enforced via a strict state machine (`VALID_TRANSITIONS`), invalid transitions return a descriptive `400` with allowed next states
- **Coupon management** — create, list, toggle active/inactive, delete coupons
- All admin routes guarded by `require_roles("admin")` dependency

### 🎟️ Coupon & Discount Engine *(New)*
- **Two discount types** — `PERCENTAGE` (e.g. 20% off) and `FLAT` (e.g. ₹100 off)
- **Usage limits** — global `max_uses` cap per coupon; tracked via `used_count`
- **Per-user usage tracking** — `CouponUsage` table prevents a single user from reusing a coupon
- **Minimum order value guard** — `min_order_value` field; coupon rejected if cart subtotal is below threshold
- **Expiry enforcement** — `valid_until` datetime; expired coupons raise descriptive `400`
- **Active flag** — admin can enable/disable coupons without deleting them
- **Atomic usage increment** — `used_count` updated in the same transaction as order creation to prevent race conditions
- **Checkout integration** — coupon applied at checkout; `coupon_discount` stored on the `Order` for audit trail
- **Case-insensitive code lookup** — coupon codes stored and matched uppercase-normalized
- **Admin CRUD** — full create/list/toggle/delete via `/api/v1/admin/coupons`
- Apply via `POST /api/v1/orders/checkout` with `coupon_code` field in the request body

### 🛍️ Catalog
- Category management with **self-referential parent/child hierarchy** (slug-indexed)
- Product CRUD with **soft delete** — deleted products hidden from listings but retained for order history integrity
- JSONB `attributes` field for flexible, schema-less product metadata
- Pagination support on product listings

### 🛒 Cart
- Auto-created cart on first access — no explicit cart creation step required
- **Ghost product cleanup** — soft-deleted products are silently removed from carts on fetch
- Real-time **stock validation** on add and update
- **Quantity decrement shortcut** — decrements by 1, auto-removes item at zero
- ORM-level `total_price` property computed from relationships
- `UniqueConstraint(cart_id, product_id)` — duplicate adds merge quantities

### 📦 Orders & Checkout
- **Razorpay-first checkout** — Razorpay order ID created *before* any DB write, eliminating stock-leak on gateway failure
- **Cart → Order conversion** in a single atomic DB transaction after Razorpay confirms
- **18% GST** on subtotal; ₹50 flat shipping waived for orders above ₹500
- **Coupon discount** applied after GST and before shipping calculation
- **Minimum order guard** — rejects checkout below ₹1 (Razorpay minimum in paise)
- **Atomic stock decrement** — concurrent over-purchase blocked at DB level with rowcount check
- `price_at_purchase` + `product_name` snapshot on each `OrderItem` — historically accurate even after price/name changes
- **Address snapshot** saved on order — correct shipping record even if user later deletes the address
- `OrderStatus` state machine: `pending → paid → processing → shipped → delivered / cancelled`

### ❌ Order Cancellation
- Users can cancel their own orders in `PENDING`, `PAID`, or `PROCESSING` states
- **Atomic stock rollback** — stock quantity restored via a direct DB `UPDATE` (not in-memory) for each cancelled item
- **Coupon usage rollback** — `used_count` decremented when a coupon-applied order is cancelled
- **Guard rails** — `SHIPPED` and `DELIVERED` orders cannot be cancelled; returns descriptive `400`
- Full rollback on any exception — no partial state left in DB

### 💳 Razorpay Payment Integration
- **Live Razorpay SDK** with `asyncio.get_running_loop() + run_in_executor` for non-blocking calls
- Checkout response returns `razorpay_order_id`, `amount`, `currency`, and `key` — ready for frontend SDK
- **Cryptographic signature verification** via `client.utility.verify_payment_signature`
- **Authorization check on verification** — users can only verify their own transactions
- **Race condition protection** — already-`SUCCESS` transactions are short-circuited
- On verified payment: `Transaction.status → SUCCESS`, `Order.status → PAID` updated atomically
- On failed signature: `Transaction.status → FAILED` is recorded; fraud attempt logged with warning

### 🔔 Razorpay Webhook Handler
- **Complete server-side payment confirmation** via `POST /api/v1/webhooks/razorpay`
- **Immediate audit logging** — every incoming event is persisted to `webhook_events` table *before* any business logic runs, ensuring no event is ever lost
- **HMAC-SHA256 signature verification** — raw request body hashed with `RAZORPAY_WEBHOOK_SECRET`; invalid signatures raise an exception and are logged
- **Idempotency guard** — duplicate `payment.captured` events for an already-`SUCCESS` transaction are short-circuited safely
- **`payment.captured` event handling** — atomically updates `Transaction.status → SUCCESS` and `Order.status → PAID` in a single commit
- **`order.paid` event** — recognized and extensible for future handling
- **Isolation from email failures** — invoice email is queued via Celery *after* the DB commit; email queue failures log a warning but never roll back a completed payment
- Always returns `200 OK` to Razorpay even on business-logic errors (`error_logged` status) to prevent unnecessary retries from the gateway

### ⚙️ Celery Async Task — Invoice Email
- **HTML invoice email** dispatched as a Celery background task after every confirmed payment (both via `/verify-payment` and webhook)
- Email renders: Order ID, User ID, total amount paid, and applied coupon discount (if any)
- **Auto-retry on failure** — Celery retries up to 3 times with a 60-second countdown on SMTP or network errors
- Fully decoupled from the payment commit — email failures never affect payment status
- Celery broker and result backend both backed by the existing authenticated Redis instance

### 📍 Address Book
- Full CRUD with **soft delete** — addresses used in past orders are never hard-deleted
- `AddressType` enum — `home`, `office`, `other` (enforced at DB level via `SQLEnum`)
- **Auto-default** — first address added is automatically set as default
- **Atomic default switching** — race-condition safe; only one address can be default at a time
- User-scoped queries — users cannot access or modify each other's addresses

### ⚙️ Developer Experience
- **Modular model architecture** — models split across `user`, `product`, `cart`, `order`, `address`, `transaction`, `coupon`
- **Service layer pattern** — all business logic in `app/services/`, routes stay thin
- **Async SQLAlchemy** with `asyncpg` driver throughout
- **Alembic** migration support for modular schema evolution
- **System-wide structured logging** via `logging_config.py`
- **Celery** worker infrastructure with active async task support (invoice email delivery)
- **Schemathesis** + **pytest** in dependencies for API contract testing

---

## Architecture & Project Structure

```text
E-Commerce/
├── alembic/                          # Database migration scripts
│   ├── versions/
│   ├── env.py
│   └── archived/
├── app/
│   ├── api/
│   │   ├── dependencies.py           # get_current_user, require_roles, auth guards
│   │   └── v1/
│   │       ├── auth.py               # All auth endpoints
│   │       ├── products.py           # Catalog & category endpoints
│   │       ├── cart.py               # Cart management endpoints
│   │       ├── order.py              # Checkout, verify-payment, cancel, order history
│   │       ├── address.py            # Address book endpoints
│   │       ├── users.py              # User profile & personal order history
│   │       ├── admin.py              # Admin panel — products, orders & coupons
│   │       └── webhooks.py           # Razorpay webhook receiver
│   ├── core/
│   │   ├── config.py                 # Pydantic settings (env-driven, incl. Razorpay + Webhook)
│   │   ├── redis.py                  # Redis client + rate limiting logic
│   │   ├── security.py               # JWT creation, blacklist, Argon2 hashing
│   │   └── logging_config.py         # Structured logging setup
│   ├── db/
│   │   ├── models/
│   │   │   ├── user.py               # User model
│   │   │   ├── product.py            # Product, Category (self-referential)
│   │   │   ├── cart.py               # Cart, CartItem
│   │   │   ├── order.py              # Order, OrderItem, OrderStatus enum
│   │   │   ├── address.py            # Address, AddressType enum
│   │   │   ├── transaction.py        # Razorpay Transaction
│   │   │   ├── coupon.py             # Coupon, CouponUsage                      ← New
│   │   │   └── webhook_event.py      # WebhookEvent audit log
│   │   ├── base.py
│   │   ├── base_class.py
│   │   └── session.py                # Async session factory + get_db
│   ├── schemas/
│   │   ├── user.py                   # UserOut, UserUpdate (phone validator)
│   │   ├── product.py                # ProductCreate, ProductUpdate, ProductResponse
│   │   ├── cart.py
│   │   ├── order.py                  # OrderOut, CheckoutRequest, PaymentVerifyRequest, OrderStatusUpdate
│   │   ├── coupon.py                 # CouponCreate, CouponOut, CouponApplyRequest  ← New
│   │   └── address.py
│   ├── services/
│   │   ├── cart_service.py           # CartService (full cart lifecycle)
│   │   ├── order_service.py          # checkout (with coupon), verify_payment, cancel, admin order fns
│   │   ├── coupon_service.py         # CouponService — validate, apply, rollback    ← New
│   │   ├── product_service.py        # ProductService (CRUD, soft delete, admin list)
│   │   ├── category_service.py       # CatalogService
│   │   ├── address_service.py        # AddressService (default, soft delete)
│   │   ├── user_service.py           # update_user_profile (with row lock)
│   │   ├── webhook_service.py        # RazorpayWebhookService (verify + handle)
│   │   └── utils.py
│   ├── utils/
│   │   └── email.py                  # FastAPI-Mail background email sender
│   ├── worker/
│   │   ├── celery_app.py             # Celery app instance (Redis broker + backend)
│   │   └── tasks.py                  # send_invoice_email Celery task
│   └── main.py                       # FastAPI app, all router registrations
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── alembic.ini
```

---

## Authentication System — Deep Dive

### Registration & Email Verification

```
POST /auth/register
  → Validates email uniqueness (case-insensitive)
  → Hashes password with Argon2
  → Creates User with is_active=False
  → Dispatches verification email via BackgroundTask

GET /auth/verify?token=<token>
  → Validates type == "email_verification"
  → Sets user.is_active = True
  → Blacklists token (single-use)

POST /auth/resend-verification
  → Generic response (no email enumeration)
  → 2-minute Redis cooldown per email
```

### Login & Token Issuance

```
POST /auth/login
  → Rate limit #1: IP-based        (5 attempts / 60s)
  → Rate limit #2: Username-based  (5 attempts / 60s)  ← blocks distributed attacks
  → Argon2 verify_and_update (re-hashes on algo upgrade)
  → Blocks login if is_active == False → 403
  → Returns: access_token (30min) + refresh_token (7d)
```

### Token Validation Chain (every protected route)

```
1. Redis blacklist check          → reject revoked tokens instantly
2. JWT decode + claims validation → type=access, UUID sub, exp in future
3. User lookup by UUID            → no username index scan
4. Session invalidation check     → token.iat < user.password_changed_at → reject
5. is_active check                → reject unverified / disabled accounts
```

### Token Refresh, Logout & Password Reset

```
POST /auth/refresh
  → Blacklisted refresh token → 401 "Token compromised" (theft detection)
  → Blacklists old token, issues new pair (full rotation)

POST /auth/logout
  → Blacklists access token with exact remaining TTL

POST /auth/reset-password
  → Validates token type + email match
  → Re-hashes password (Argon2)
  → Sets password_changed_at = now() → invalidates ALL active sessions globally
  → Blacklists reset token (single-use)
```

### Role-Based Access Control

```python
Depends(require_roles("admin"))              # Admin only
Depends(require_roles("admin", "manager"))   # Admin OR Manager
```

---

## Razorpay Payment Flow

```
POST /api/v1/orders/checkout
  ├── Validate cart is non-empty
  ├── Validate shipping address (user-owned, not deleted)
  ├── Validate & apply coupon (if coupon_code in request)
  │   → Check expiry, active status, max_uses, per-user usage, min_order_value
  ├── Compute: subtotal + 18% GST − coupon_discount + ₹50 shipping (waived above ₹500)
  ├── Guard: amount must be ≥ ₹1 (100 paise)
  ├── ── RAZORPAY FIRST (no DB writes yet) ──────────────────────────
  │   → client.order.create() via run_in_executor (non-blocking)
  │   → Razorpay fails? → Zero DB side effects
  ├── ── DB WRITES (only after Razorpay order ID received) ──────────
  │   → Create Order record (coupon_discount stored)
  │   → Atomic stock decrement per item (rowcount-checked)
  │   → Create OrderItem with price_at_purchase + product_name snapshot
  │   → Increment coupon.used_count (same transaction)
  │   → Create CouponUsage record (same transaction)
  │   → Clear Cart
  │   → Create Transaction (PENDING, razorpay_order_id saved)
  │   → Single db.commit()
  └── Response: { order, payment_details: { razorpay_order_id, amount, currency, key } }
```

---

## Razorpay Webhook Handler

```
POST /api/v1/webhooks/razorpay
  (No auth required — public endpoint, secured by HMAC signature)

  ├── 1. AUDIT LOG FIRST
  │   → Write WebhookEvent(event_type, payload, processed=False) to DB
  │   → db.commit() immediately — event is never lost
  │
  ├── 2. SIGNATURE VERIFICATION
  │   → HMAC-SHA256(raw_body, RAZORPAY_WEBHOOK_SECRET)
  │   → hmac.compare_digest() — safe against timing attacks
  │
  ├── 3. EVENT ROUTING (event_type)
  │   ├── "payment.captured" → handle_payment_success()
  │   ├── "order.paid"       → recognized, extensible
  │   └── anything else      → logged as ignored
  │
  ├── 4. handle_payment_success()
  │   → Lookup Transaction by razorpay_order_id
  │   → IDEMPOTENCY CHECK: already SUCCESS? → return True
  │   → ATOMIC UPDATE: transaction.status = SUCCESS, order.status = PAID
  │   → AFTER COMMIT: queue Celery invoice email
  │
  └── 5. MARK PROCESSED → webhook_log.processed = True → return {"status": "ok"}
```

---

## Celery Async Task — Invoice Email

After every confirmed payment (via webhook or `/verify-payment`), an HTML invoice email is dispatched as a non-blocking Celery background task.

```python
send_invoice_email.delay(
    user_email=...,
    user_id=...,
    order_id=...,
    amount=...,
    coupon_discount=...   # included if coupon was applied
)
```

- **Task name:** `send_invoice_email`
- **Broker & backend:** Redis (same authenticated instance as token blacklist)
- **Retry policy:** `max_retries=3`, `countdown=60` seconds between retries
- **Template:** Styled HTML receipt with Order ID, User ID, total paid, and discount applied
- **Subject:** `Payment Receipt - Order #<last 6 chars of order_id>`
- **SMTP:** Synchronous `smtplib` (Celery-safe) with optional STARTTLS support
- **Failure isolation:** Email queue errors are logged as warnings; the payment DB state is never rolled back

---

## Order State Machine

```
PENDING ──────┬──► PAID ──► PROCESSING ──► SHIPPED ──► DELIVERED
              │     │            │
              └─────┴────────────┴──────────────────────► CANCELLED
                           (user can cancel up to PROCESSING)
                           (admin can cancel up to PROCESSING)
                           (SHIPPED and DELIVERED are terminal for cancellation)
```

| From | Allowed Transitions |
|------|-------------------|
| `PENDING` | `PAID`, `CANCELLED` |
| `PAID` | `PROCESSING`, `CANCELLED` |
| `PROCESSING` | `SHIPPED`, `CANCELLED` |
| `SHIPPED` | `DELIVERED` |
| `DELIVERED` | *(terminal)* |
| `CANCELLED` | *(terminal)* |

---

## Coupon & Discount Engine

### How it works

```
User applies coupon at checkout → POST /api/v1/orders/checkout
  {
    "address_id": "...",
    "coupon_code": "SAVE20"   ← optional
  }

CouponService.validate_and_apply(code, user_id, subtotal):
  1. Lookup coupon by code (case-insensitive, uppercase-normalized)
  2. Check coupon.is_active == True                  → 400 if inactive
  3. Check coupon.valid_until >= now()               → 400 if expired
  4. Check coupon.used_count < coupon.max_uses       → 400 if exhausted
  5. Check subtotal >= coupon.min_order_value        → 400 with min value in message
  6. Check CouponUsage(coupon_id, user_id) not exists → 400 "already used"
  7. Calculate discount:
       PERCENTAGE → subtotal * (value / 100)
       FLAT       → min(value, subtotal)   ← never discounts below ₹0
  8. Return discount_amount (does NOT commit — checkout transaction handles it)

On Order creation (same atomic transaction):
  → coupon.used_count += 1
  → CouponUsage(coupon_id, user_id, order_id) inserted
  → order.coupon_id = coupon.id
  → order.coupon_discount = discount_amount

On Order cancellation:
  → coupon.used_count -= 1
  → CouponUsage record deleted
  → order.coupon_discount remains for audit trail
```

### Coupon Model

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `code` | String(50) | Unique, uppercase-normalized, indexed |
| `discount_type` | Enum | `PERCENTAGE` or `FLAT` |
| `discount_value` | Numeric | % value or ₹ flat amount |
| `min_order_value` | Numeric | Minimum subtotal to apply, default 0 |
| `max_uses` | Integer | Global usage cap |
| `used_count` | Integer | Auto-incremented on use |
| `valid_until` | DateTime(tz) | Expiry datetime |
| `is_active` | Boolean | Admin toggle |
| `created_at` | DateTime | Auto-set |

### CouponUsage Model

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `coupon_id` | FK → Coupon | Indexed |
| `user_id` | FK → User | Indexed |
| `order_id` | FK → Order | For audit trail |
| `used_at` | DateTime | Auto-set |
| `UniqueConstraint` | (coupon_id, user_id) | One use per user per coupon |

---

## Admin Panel

All admin routes are under `/api/v1/admin` and require `require_roles("admin")`.

### Product Management

| Action | What it does |
|--------|-------------|
| Create product | Full product creation with auto-slug generation |
| List all products | Returns active **and** soft-deleted products — ordered by `is_deleted ASC, name ASC` |
| Partial update | Update `price`, `stock_quantity`, `description`, `attributes` — any subset |
| Soft delete | Sets `is_deleted=True`; product hidden from public but preserved for order history |

### Order Management

| Action | What it does |
|--------|-------------|
| List all orders | Platform-wide, paginated, filterable by `status` query param |
| Update order status | State-machine-validated transition; descriptive error on invalid move |

### Coupon Management

| Action | What it does |
|--------|-------------|
| Create coupon | Full coupon creation with type, value, expiry, limits |
| List coupons | All coupons with usage stats (`used_count / max_uses`) |
| Toggle active | Enable / disable a coupon without deleting it |
| Delete coupon | Hard delete (only if `used_count == 0`; else soft-disable recommended) |

---

## API Endpoints Reference

### Authentication — `/auth`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/register` | Public | Register, sends verification email |
| `POST` | `/auth/resend-verification` | Public | Resend verification (2 min cooldown) |
| `GET` | `/auth/verify` | Public | Activate account via token |
| `POST` | `/auth/login` | Public | Login, returns token pair |
| `POST` | `/auth/refresh` | Public | Rotate refresh token |
| `POST` | `/auth/logout` | Bearer | Blacklist access token |
| `POST` | `/auth/forgot-password` | Public | Trigger reset (generic response) |
| `POST` | `/auth/reset-password` | Public | Reset password, invalidate all sessions |

### Users — `/api/v1/users`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/users/me` | Bearer | Get own profile |
| `PATCH` | `/api/v1/users/me` | Bearer | Update name, email, phone |
| `GET` | `/api/v1/users/me/orders` | Bearer | Personal order history (paginated) |

### Admin Panel — `/api/v1/admin`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/admin/products` | Admin | Create product |
| `GET` | `/api/v1/admin/products` | Admin | List all products (incl. deleted) |
| `PATCH` | `/api/v1/admin/products/{id}` | Admin | Partial update product |
| `DELETE` | `/api/v1/admin/products/{id}` | Admin | Soft-delete product |
| `GET` | `/api/v1/admin/orders` | Admin | List all orders (filterable by status) |
| `PATCH` | `/api/v1/admin/orders/{id}/status` | Admin | Update order status |
| `POST` | `/api/v1/admin/coupons` | Admin | Create coupon |
| `GET` | `/api/v1/admin/coupons` | Admin | List all coupons with stats |
| `PATCH` | `/api/v1/admin/coupons/{id}/toggle` | Admin | Enable / disable coupon |
| `DELETE` | `/api/v1/admin/coupons/{id}` | Admin | Delete coupon |

### Catalog — `/api/v1/products`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/products/categories` | Public | Create category |
| `GET` | `/api/v1/products/categories` | Public | List categories |
| `POST` | `/api/v1/products/` | Public | Create product |
| `GET` | `/api/v1/products/` | Public | List active products (paginated) |
| `GET` | `/api/v1/products/{id}` | Public | Get product by ID |
| `DELETE` | `/api/v1/products/{id}` | Public | Soft-delete product |

### Cart — `/api/v1/cart`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/cart/` | Bearer | Get cart |
| `POST` | `/api/v1/cart/items` | Bearer | Add item |
| `PUT` | `/api/v1/cart/items/{id}` | Bearer | Set quantity |
| `PATCH` | `/api/v1/cart/items/{id}/decrease` | Bearer | Decrease by 1 |
| `DELETE` | `/api/v1/cart/items/{id}` | Bearer | Remove item |
| `DELETE` | `/api/v1/cart/` | Bearer | Clear cart |

### Orders — `/api/v1/orders`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/orders/checkout` | Bearer | Create Razorpay order + DB order (optional coupon) |
| `POST` | `/api/v1/orders/verify-payment` | Bearer | Verify signature, mark PAID |
| `GET` | `/api/v1/orders/` | Bearer | List paid orders |
| `GET` | `/api/v1/orders/{id}` | Bearer | Get order details |
| `PATCH` | `/api/v1/orders/{id}/cancel` | Bearer | Cancel order + restore stock + rollback coupon |

### Addresses — `/api/v1/addresses`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/addresses/` | Bearer | List addresses |
| `POST` | `/api/v1/addresses/` | Bearer | Add address |
| `PATCH` | `/api/v1/addresses/{id}` | Bearer | Update address |
| `PATCH` | `/api/v1/addresses/{id}/default` | Bearer | Set as default |
| `DELETE` | `/api/v1/addresses/{id}` | Bearer | Soft-delete address |

### Webhooks — `/api/v1/webhooks`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/webhooks/razorpay` | HMAC Signature | Receive Razorpay payment events |

---

## Data Models

### User
| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `username` | String(50) | Unique, alphanumeric + underscore |
| `email` | String(100) | Unique, lowercased |
| `hashed_password` | String | Argon2 |
| `password_changed_at` | DateTime(tz) | Global session invalidation anchor |
| `full_name` | String(100) | Optional, updatable via `/users/me` |
| `phone_number` | String(20) | Optional, validated as Indian mobile |
| `is_active` | Boolean | False until email verified |
| `is_admin` | Boolean | Role flag |
| `is_deleted` | Boolean | Soft delete |

### Product & Category
- `Category` — self-referential `parent_id`, soft delete, `sub_categories` lazy-loaded via `selectin`
- `Product` — JSONB `attributes`, soft delete, slug auto-generated from name

### Cart & CartItem
- `Cart` — user-scoped, auto-created; `total_price` as ORM `@property`
- `CartItem` — `UniqueConstraint(cart_id, product_id)`, real-time stock validation

### Order & OrderItem
| Field | Notes |
|-------|-------|
| `subtotal_price` | Raw item total |
| `tax_price` | 18% GST |
| `coupon_discount` | Discount amount applied (0 if no coupon) |
| `shipping_price` | ₹50 flat, waived above ₹500 |
| `total_price` | Grand total sent to Razorpay in paise |
| `coupon_id` | FK → Coupon (nullable) |
| `shipping_address_snapshot` | Text copy frozen at checkout |
| `OrderItem.price_at_purchase` | Price frozen at checkout |
| `OrderItem.product_name` | Name frozen at checkout |
| `status` | Enforced by state machine |

### Address
| Field | Notes |
|-------|-------|
| `address_type` | Enum: `home`, `office`, `other` |
| `is_default` | One per user, atomically enforced |
| `is_deleted` | Soft delete, preserves order reference integrity |

### Transaction
| Field | Notes |
|-------|-------|
| `razorpay_order_id` | From Razorpay order creation |
| `razorpay_payment_id` | Populated after verification |
| `razorpay_signature` | Stored for audit trail |
| `status` | `PENDING` → `SUCCESS` / `FAILED` |

### Coupon & CouponUsage
See [Coupon & Discount Engine](#coupon--discount-engine) section above.

### WebhookEvent
| Field | Notes |
|-------|-------|
| `event_type` | Indexed string — e.g. `payment.captured` |
| `payload` | Full raw JSONB event for audit and replay |
| `processed` | `False` on arrival; `True` after successful handling |
| `created_at` | Auto-set at insert |

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

# Redis
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

# For LAN/mobile testing
EMAIL_VERIFY_BASE_URL=http://192.168.x.x:8001

# Razorpay (get from razorpay.com/app/keys)
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_SECRET_KEY=your_razorpay_secret
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret
```

### 3. Start all services
```bash
docker compose up --build -d
```

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

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL async connection string |
| `SECRET_KEY` | ✅ | JWT signing key (min 32 chars) |
| `ALGORITHM` | ✅ | JWT algorithm (`HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | Access token lifetime |
| `REDIS_HOST` | ✅ | Redis hostname |
| `REDIS_PORT` | ✅ | Redis port (default `6379`) |
| `REDIS_PASSWORD` | ✅ | Redis auth password |
| `MAIL_USERNAME` | ✅ | SMTP username |
| `MAIL_PASSWORD` | ✅ | SMTP password / app password |
| `MAIL_FROM` | ✅ | Sender email |
| `MAIL_PORT` | ✅ | SMTP port |
| `MAIL_SERVER` | ✅ | SMTP server |
| `MAIL_STARTTLS` | ✅ | `True`/`False` |
| `MAIL_SSL_TLS` | ✅ | `True`/`False` |
| `EMAIL_VERIFY_BASE_URL` | ✅ | Base URL for verification links |
| `RAZORPAY_KEY_ID` | ✅ | Razorpay API key ID |
| `RAZORPAY_SECRET_KEY` | ✅ | Razorpay secret key |
| `RAZORPAY_WEBHOOK_SECRET` | ✅ | Razorpay webhook secret (from Dashboard → Webhooks) |

---

## Quick Verification Checklist

1. **Register** → `POST /auth/register`
2. **Verify email** → `GET /auth/verify?token=...`
3. **Login** → `POST /auth/login`, save tokens
4. **View profile** → `GET /api/v1/users/me`
5. **Update profile** → `PATCH /api/v1/users/me`
6. **Add address** → `POST /api/v1/addresses/`
7. **Add items to cart** → `POST /api/v1/cart/items`
8. **Create coupon (admin)** → `POST /api/v1/admin/coupons`
9. **Checkout with coupon** → `POST /api/v1/orders/checkout` with `coupon_code` → invoice email queued via Celery
10. **Verify payment** → `POST /api/v1/orders/verify-payment`
11. **Webhook test** → `POST /api/v1/webhooks/razorpay` with valid `x-razorpay-signature` header
12. **Cancel order** → `PATCH /api/v1/orders/{id}/cancel` (only PENDING/PAID/PROCESSING; coupon usage rolled back)
13. **Admin: update order status** → `PATCH /api/v1/admin/orders/{id}/status`
14. **Rate limit test** → 6+ bad login attempts → `429`; wait 60s → works again

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.135 |
| Language | Python 3.11+ |
| Database | PostgreSQL 15 (`asyncpg`) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Cache / Blacklist | Redis (Authenticated, Alpine) |
| Password Hashing | Argon2 (via passlib) |
| JWT | python-jose |
| Email | FastAPI-Mail / SMTP |
| Payments | Razorpay SDK |
| Webhooks | HMAC-SHA256 (standard library `hmac`) |
| Task Queue | Celery (active — invoice email delivery) |
| Containerization | Docker / Docker Compose |
| Validation | Pydantic v2 |
| Testing | pytest, Schemathesis |

---

## Roadmap

- [x] JWT Authentication with email verification
- [x] Redis-backed token blacklist & rate limiting
- [x] Modular model architecture
- [x] Catalog — Products & Categories
- [x] Full Cart lifecycle
- [x] Order & Checkout with atomic stock management
- [x] Address Book with soft delete & default management
- [x] Razorpay live payment integration & signature verification
- [x] Order Cancellation with atomic stock rollback
- [x] Admin Panel — product & order management
- [x] Order state machine with validated transitions
- [x] User Profile — fetch & update with phone validation
- [x] Razorpay webhook handler — server-side payment confirmation with audit log
- [x] Celery async tasks — HTML invoice email on payment confirmation
- [x] Coupon & Discount Engine — percentage/flat, per-user tracking, expiry, usage limits
- [ ] Redis-backed cart caching
- [ ] Sentry error tracking integration
- [ ] Product reviews & ratings
- [ ] Wishlist / saved items

---

## Contributing

Contributions, issues, and feature requests are welcome. Check the [issues page](https://github.com/Vishwam401/E-commerce/issues) to get started.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/Vishwam401">Vishwam401</a>
</p>
