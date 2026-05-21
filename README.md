<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=28&duration=3000&pause=1000&color=00BFA6&center=true&vCenter=true&multiline=true&width=600&height=80&lines=%CE%B1+Alpha-Commerce;Production-Grade+E-Commerce+Backend" alt="Alpha-Commerce" />
</p>

<p align="center">
  <strong>A fully async FastAPI backend with live payments, multi-layer auth, and enterprise-grade inventory — built from scratch.</strong>
</p>

<p align="center">
  <a href="#-quick-start"><img src="https://img.shields.io/badge/-Quick_Start-00BFA6?style=for-the-badge&logoColor=white" /></a>
  <a href="#-architecture"><img src="https://img.shields.io/badge/-Architecture-6C63FF?style=for-the-badge&logoColor=white" /></a>
  <a href="#-api-reference"><img src="https://img.shields.io/badge/-API_Docs-FF6B6B?style=for-the-badge&logoColor=white" /></a>
  <a href="#-deep-dives"><img src="https://img.shields.io/badge/-Deep_Dives-FFA726?style=for-the-badge&logoColor=white" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-Alpine-DC382D?style=flat-square&logo=redis&logoColor=white" />
  <img src="https://img.shields.io/badge/Razorpay-Live-02042B?style=flat-square&logo=razorpay&logoColor=white" />
  <img src="https://img.shields.io/badge/Celery-5.x-37814A?style=flat-square&logo=celery&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white" />
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/Vishwam401/E-commerce?style=flat-square&color=00BFA6" />
  <img src="https://img.shields.io/github/forks/Vishwam401/E-commerce?style=flat-square&color=6C63FF" />
  <img src="https://img.shields.io/github/last-commit/Vishwam401/E-commerce?style=flat-square&color=FFA726" />
</p>

---

## ✨ Highlights

<table>
<tr>
<td width="50%">

**🔐 Multi-Layer Security**
- Argon2 password hashing with auto-rehash
- JWT access + refresh tokens with rotation
- Redis token blacklist (instant revocation)
- Refresh token theft detection
- Dual-layer rate limiting (IP + username)
- Session invalidation on password change

</td>
<td width="50%">

**💳 Live Payment Processing**
- Razorpay order creation via `run_in_executor`
- Gateway-first design (zero DB side effects on failure)
- Cryptographic signature verification
- Server-side webhook with HMAC-SHA256
- Audit log written before business logic
- Idempotent duplicate event handling

</td>
</tr>
<tr>
<td width="50%">

**📦 Inventory Audit Trail**
- Immutable `StockMovement` entries for every change
- `before → after` snapshots on each operation
- Atomic row-level stock guards (no oversell)
- Low-stock alerts & reorder point monitoring
- Admin restock, adjust, threshold management

</td>
<td width="50%">

**🎟️ Coupon & Discount Engine**
- Percentage & flat discounts with cap support
- Per-user + global usage limits
- Date-range validity with timezone awareness
- Race-condition protection via `SELECT ... FOR UPDATE`
- Full rollback on order cancellation

</td>
</tr>
<tr>
<td width="50%">

**⚙️ Async Task Queue**
- Celery workers with Redis broker
- HTML invoice emails (styled, auto-retry ×3)
- Email failures never roll back payments
- Decoupled from the payment commit path

</td>
<td width="50%">

**🏗️ Clean Architecture**
- Service-layer pattern (thin routes, fat services)
- 20+ domain-specific exceptions
- 6 global error handlers (zero raw exceptions)
- Pydantic v2 schemas for all I/O
- Alembic migrations, Docker-first setup

</td>
</tr>
</table>

---

## 🏛 Architecture

```mermaid
graph TB
    subgraph Client
        FE["🖥️ Frontend / API Consumer"]
    end

    subgraph FastAPI["⚡ FastAPI Application"]
        direction TB
        R1["Auth Router"]
        R2["Orders Router"]
        R3["Admin Router"]
        R4["Webhook Router"]
        R5["Cart · Products · Coupons"]
        
        SL["Service Layer<br/><i>auth · order · coupon · inventory · webhook · cart</i>"]
        
        ORM["Async SQLAlchemy + asyncpg"]
    end

    subgraph Data["💾 Data Layer"]
        PG[("PostgreSQL 15<br/>Primary Database")]
        RD[("Redis Alpine<br/>Blacklist · Rate Limit · Broker")]
    end

    subgraph Workers["👷 Background"]
        CW["Celery Worker<br/>Invoice Emails · SMTP"]
    end

    subgraph External["🌐 External"]
        RZP["Razorpay Gateway<br/>Orders · Payments · Webhooks"]
    end

    FE -->|"REST / HTTP"| R1 & R2 & R3 & R5
    RZP -->|"Webhook POST"| R4
    R1 & R2 & R3 & R4 & R5 --> SL
    SL --> ORM
    ORM --> PG
    SL -->|"Blacklist · Rate Limit"| RD
    SL -->|"Order Create · Verify"| RZP
    SL -->|"task.delay()"| CW
    CW -->|"Broker + Backend"| RD

    style FastAPI fill:#1a1a2e,stroke:#00BFA6,stroke-width:2px,color:#fff
    style Data fill:#16213e,stroke:#6C63FF,stroke-width:2px,color:#fff
    style Workers fill:#0f3460,stroke:#FFA726,stroke-width:2px,color:#fff
    style External fill:#1a1a2e,stroke:#FF6B6B,stroke-width:2px,color:#fff
    style Client fill:#1a1a2e,stroke:#00BFA6,stroke-width:2px,color:#fff
```

---

## 🔄 Deep Dives

### 🔐 Authentication Flow

> **5-step validation chain** on every protected request — from Redis blacklist check to session invalidation detection.

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI
    participant RD as Redis
    participant DB as PostgreSQL

    Note over C,DB: 📝 Registration
    C->>API: POST /auth/register
    API->>API: Validate email uniqueness (case-insensitive)
    API->>API: Hash password (Argon2)
    API->>DB: Create User (is_active = false)
    API->>C: Dispatch verification email (BackgroundTask)
    
    Note over C,DB: ✅ Email Verification
    C->>API: GET /auth/verify?token=<token>
    API->>API: Validate token type = "email_verification"
    API->>DB: Set is_active = true
    API->>RD: Blacklist token (single-use)
    API->>C: 200 OK — Account activated

    Note over C,DB: 🔑 Login
    C->>API: POST /auth/login
    API->>RD: Rate limit check — IP (5/60s)
    API->>RD: Rate limit check — Username (5/60s)
    API->>DB: Fetch user, Argon2 verify_and_update
    API->>API: Reject if is_active = false → 403
    API->>C: { access_token (30min), refresh_token (7d) }

    Note over C,DB: 🛡️ Protected Request — 5-Step Chain
    C->>API: GET /api/v1/users/me [Bearer token]
    API->>RD: ① Blacklist check → reject revoked tokens
    API->>API: ② JWT decode + claims (type=access, UUID sub, exp)
    API->>DB: ③ User lookup by UUID
    API->>API: ④ Session check: iat ≥ password_changed_at?
    API->>API: ⑤ is_active check
    API->>C: 200 — User profile
```

<details>
<summary><b>🔄 Token Lifecycle — Refresh, Logout & Theft Detection</b></summary>

```mermaid
flowchart LR
    subgraph Refresh["POST /auth/refresh"]
        R1["Receive refresh token"] --> R2{"Blacklisted?"}
        R2 -- "Yes" --> R3["🚨 401 — Token compromised<br/><i>Theft detection triggered</i>"]
        R2 -- "No" --> R4["Blacklist old pair"]
        R4 --> R5["Issue new access + refresh"]
    end

    subgraph Logout["POST /auth/logout"]
        L1["Receive access token"] --> L2["Blacklist with remaining TTL"]
        L2 --> L3["✅ Token revoked"]
    end

    subgraph Reset["POST /auth/reset-password"]
        P1["New password"] --> P2["Re-hash (Argon2)"]
        P2 --> P3["Set password_changed_at = now()"]
        P3 --> P4["⚡ ALL active sessions invalidated"]
        P4 --> P5["Blacklist reset token (single-use)"]
    end

    style Refresh fill:#1a1a2e,stroke:#00BFA6,color:#fff
    style Logout fill:#1a1a2e,stroke:#6C63FF,color:#fff
    style Reset fill:#1a1a2e,stroke:#FF6B6B,color:#fff
```

</details>

---

### 💳 Payment & Checkout Flow

> **Design principle:** Razorpay order is created *before* any database writes. A gateway failure leaves zero side effects.

```mermaid
flowchart TD
    A["POST /orders/checkout"] --> B["Validate cart & shipping address"]
    B --> C{"Coupon attached?"}
    C -- "Yes" --> D["Validate coupon<br/><i>active · date range · usage limits · min order</i>"]
    D --> E["Calculate discount<br/><i>% with cap or flat amount</i>"]
    C -- "No" --> F["Skip coupon"]
    E --> F
    
    F --> G["💰 Price Computation<br/><code>subtotal + 18% GST − discount + ₹50 shipping</code><br/><i>Shipping waived above ₹500</i>"]
    G --> H{"amount ≥ ₹1?"}
    H -- "No" --> I["❌ MinimumOrderError"]
    H -- "Yes" --> J

    subgraph RZP["☁️ Razorpay First — No DB Writes Yet"]
        J["client.order.create()<br/><i>via run_in_executor (non-blocking)</i>"]
    end

    J -- "Gateway fails" --> K["❌ Zero DB side effects"]
    J -- "Success" --> L

    subgraph TX["🔒 Single Atomic DB Transaction"]
        L["Create Order<br/><i>with coupon_discount for audit</i>"]
        L --> M["Atomic stock decrement per item<br/><i>rowcount-checked — no oversell</i>"]
        M --> N["Create OrderItems<br/><i>price_at_purchase + name snapshot</i>"]
        N --> O["Record StockMovement (SALE)"]
        O --> P["Increment coupon.total_used_count"]
        P --> Q["Insert CouponUsage record"]
        Q --> R["Clear cart"]
        R --> S["Create Transaction (PENDING)"]
        S --> T["db.commit()"]
    end

    T --> U["✅ Return razorpay_order_id + key"]

    style RZP fill:#0f3460,stroke:#FF6B6B,stroke-width:2px,color:#fff
    style TX fill:#1a1a2e,stroke:#00BFA6,stroke-width:2px,color:#fff
```

<details>
<summary><b>✅ Payment Verification (Client-Side Confirmation)</b></summary>

```mermaid
flowchart TD
    A["POST /orders/verify-payment"] --> B["Authorization: user owns this transaction?"]
    B --> C{"Already SUCCESS?"}
    C -- "Yes" --> D["✅ Short-circuit — idempotent"]
    C -- "No" --> E["Razorpay cryptographic signature verification"]
    E -- "Valid ✅" --> F["transaction.status = SUCCESS<br/>order.status = PAID"]
    E -- "Invalid ❌" --> G["transaction.status = FAILED<br/>🚨 Fraud attempt logged"]
    F --> H["After commit → queue Celery invoice email"]

    style A fill:#1a1a2e,stroke:#00BFA6,color:#fff
```

</details>

---

### 📬 Webhook Handler

> **Reliability-first:** audit log persisted *before* any business logic. Idempotent on duplicates. Email failures never affect payment state.

```mermaid
flowchart TD
    A["POST /webhooks/razorpay<br/><i>Public — secured by HMAC only</i>"] --> B

    subgraph S1["Step 1 · Audit Log First"]
        B["Write WebhookEvent to DB<br/><i>persisted even if everything else fails</i>"]
    end

    B --> C

    subgraph S2["Step 2 · Signature Verification"]
        C["HMAC-SHA256(raw_body, secret)<br/><i>hmac.compare_digest — timing-attack safe</i>"]
    end

    C -- "Invalid" --> D["⚠️ Log + return 200<br/><i>Prevent Razorpay retry storm</i>"]
    C -- "Valid" --> E

    subgraph S3["Step 3 · Event Routing"]
        E{"event type?"}
        E -- "payment.captured" --> F["handle_payment_success()"]
        E -- "order.paid" --> G["Recognized — extensible"]
        E -- "other" --> H["Logged as ignored"]
    end

    subgraph S4["Step 4 · Payment Success"]
        F --> I{"Already SUCCESS?"}
        I -- "Yes" --> J["✅ Idempotent no-op"]
        I -- "No" --> K["Atomic update:<br/>transaction → SUCCESS<br/>order → PAID"]
        K --> L["Queue Celery invoice email"]
    end

    L --> M["Step 5 · Mark webhook processed → return 200"]

    style S1 fill:#16213e,stroke:#FFA726,stroke-width:2px,color:#fff
    style S2 fill:#16213e,stroke:#FF6B6B,stroke-width:2px,color:#fff
    style S3 fill:#16213e,stroke:#6C63FF,stroke-width:2px,color:#fff
    style S4 fill:#16213e,stroke:#00BFA6,stroke-width:2px,color:#fff
```

---

### 📦 Order Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING
    
    PENDING --> PAID : Payment verified
    PENDING --> CANCELLED : User/Admin cancel
    
    PAID --> PROCESSING : Admin action
    PAID --> CANCELLED : User/Admin cancel
    
    PROCESSING --> SHIPPED : Admin action
    PROCESSING --> CANCELLED : User/Admin cancel
    
    SHIPPED --> DELIVERED : Admin action
    
    note right of CANCELLED
        Terminal state.
        Triggers: stock rollback + coupon rollback
    end note
    
    note right of DELIVERED
        Terminal state.
        No further transitions.
    end note
```

<details>
<summary><b>♻️ Cancellation — What Gets Rolled Back</b></summary>

```mermaid
flowchart LR
    A["PATCH /orders/{id}/cancel"] --> B{"Status?"}
    B -- "SHIPPED / DELIVERED" --> C["❌ 400 — Cannot cancel"]
    B -- "PENDING / PAID / PROCESSING" --> D["Atomic stock rollback<br/><i>DB UPDATE per item</i>"]
    D --> E["Record StockMovement (RETURN)"]
    E --> F["coupon.total_used_count -= 1"]
    F --> G["Delete CouponUsage record"]
    G --> H["order.status = CANCELLED"]
    H --> I["✅ Full rollback on any exception"]

    style A fill:#1a1a2e,stroke:#FF6B6B,color:#fff
```

</details>

---

### 🎟️ Coupon Engine

> **7-step validation** with race-condition protection at checkout using `SELECT ... FOR UPDATE`.

```mermaid
flowchart TD
    A["User applies coupon"] --> B["Normalize code → UPPERCASE"]
    B --> C["① Lookup by code"]
    C --> D["② is_active check"]
    D --> E["③ Date range: valid_from ≤ now ≤ valid_until"]
    E --> F["④ Global usage: total_used < max_total_uses"]
    F --> G["⑤ Per-user usage: user_count < max_per_user"]
    G --> H["⑥ Min order value: subtotal ≥ min_order_value"]
    H --> I["⑦ Discount calculation"]
    
    I --> J{"Type?"}
    J -- "PERCENTAGE" --> K["subtotal × (value/100)<br/>capped at max_discount_cap"]
    J -- "FLAT" --> L["flat_value<br/>capped at subtotal"]
    K --> M["✅ Applied to cart"]
    L --> M

    style A fill:#1a1a2e,stroke:#FFA726,color:#fff
```

<details>
<summary><b>🔄 Coupon Lifecycle — Apply → Checkout → Cancellation Rollback</b></summary>

```mermaid
flowchart LR
    subgraph Cart["🛒 Cart Phase"]
        A1["Apply coupon"] --> A2["Discount preview stored on cart"]
    end

    subgraph Checkout["💳 Checkout Phase"]
        B1["Re-validate under FOR UPDATE lock<br/><i>Race-condition safe</i>"]
        B1 --> B2["coupon.total_used_count += 1"]
        B2 --> B3["Insert CouponUsage record"]
        B3 --> B4["Snapshot discount on order"]
    end

    subgraph Cancel["❌ Cancellation Rollback"]
        C1["coupon.total_used_count -= 1"]
        C1 --> C2["Delete CouponUsage record"]
        C2 --> C3["discount preserved on order<br/><i>for historical record</i>"]
    end

    Cart --> Checkout --> Cancel

    style Cart fill:#16213e,stroke:#00BFA6,color:#fff
    style Checkout fill:#16213e,stroke:#6C63FF,color:#fff
    style Cancel fill:#16213e,stroke:#FF6B6B,color:#fff
```

</details>

---

### 📊 Inventory System

> Every stock change — sale, cancellation, restock, or admin adjustment — is recorded as an **immutable `StockMovement` entry** with `before → after` snapshots.

```mermaid
flowchart LR
    subgraph Triggers["Trigger Events"]
        T1["🛒 Checkout<br/>→ SALE"]
        T2["❌ Cancellation<br/>→ RETURN"]
        T3["📥 Admin Restock<br/>→ RESTOCK"]
        T4["⚙️ Admin Adjust<br/>→ ADJUSTMENT"]
    end

    subgraph Record["StockMovement Record"]
        R["product_id<br/>movement_type<br/>quantity_changed (signed ±)<br/>quantity_before → quantity_after<br/>reference_id (order UUID)<br/>reason (mandatory for ADJUSTMENT)<br/>performed_by (admin FK)<br/>created_at (immutable)"]
    end

    T1 & T2 & T3 & T4 --> Record

    style Triggers fill:#16213e,stroke:#FFA726,stroke-width:2px,color:#fff
    style Record fill:#1a1a2e,stroke:#00BFA6,stroke-width:2px,color:#fff
```

---

### ⚙️ Celery Invoice Email Pipeline

```mermaid
flowchart LR
    A["Payment confirmed<br/><i>webhook or /verify-payment</i>"] --> B["send_invoice_email.delay()"]
    B --> C["Redis Broker"]
    C --> D["Celery Worker"]
    D --> E["Build styled HTML email"]
    E --> F["SMTP send<br/><i>optional STARTTLS</i>"]
    F -- "Success" --> G["✅ Invoice delivered"]
    F -- "Failure" --> H["🔄 Retry (max 3, 60s interval)"]
    H --> F

    style A fill:#1a1a2e,stroke:#00BFA6,color:#fff
    style D fill:#0f3460,stroke:#FFA726,color:#fff
```

> **Key guarantee:** Email failures are logged as warnings — the payment DB state is **never** rolled back.

---

### 🚨 Exception Architecture

```mermaid
flowchart TD
    EX["Exception (Python)"]
    EX --> AE["AppException (Base)<br/><i>status_code · error_code · message</i>"]
    
    AE --> BR["BadRequestError (400)"]
    AE --> UA["UnauthorizedError (401)"]
    AE --> FB["ForbiddenError (403)"]
    AE --> NF["NotFoundError (404)"]
    AE --> CF["ConflictError (409)"]
    AE --> RL["RateLimitError (429)"]
    AE --> SU["ServiceUnavailableError (503)"]

    BR --> BR1["CartEmptyError"]
    BR --> BR2["InsufficientStockError"]
    BR --> BR3["PaymentVerificationError"]
    BR --> BR4["OrderCancellationError"]
    BR --> BR5["CouponExpiredError"]
    BR --> BR6["NegativeStockError"]
    
    UA --> UA1["AuthenticationError"]
    UA --> UA2["TokenCompromisedError"]
    UA --> UA3["SessionInvalidatedError"]
    
    NF --> NF1["CouponNotFoundError"]
    
    CF --> CF1["EmailAlreadyExistsError"]
    CF --> CF2["UsernameAlreadyExistsError"]
    
    SU --> SU1["PaymentGatewayError"]
    SU --> SU2["DatabaseError"]

    style AE fill:#16213e,stroke:#00BFA6,stroke-width:2px,color:#fff
    style BR fill:#1a1a2e,stroke:#FF6B6B,color:#fff
    style UA fill:#1a1a2e,stroke:#FFA726,color:#fff
    style FB fill:#1a1a2e,stroke:#6C63FF,color:#fff
    style NF fill:#1a1a2e,stroke:#6C63FF,color:#fff
    style CF fill:#1a1a2e,stroke:#6C63FF,color:#fff
    style RL fill:#1a1a2e,stroke:#FFA726,color:#fff
    style SU fill:#1a1a2e,stroke:#FF6B6B,color:#fff
```

6 global handlers catch everything — **no raw exceptions reach the client:**

| Handler | Catches | Response |
|:---|:---|:---|
| `app_exception_handler` | All `AppException` subclasses | `{ error_code, message, path }` |
| `validation_exception_handler` | Pydantic `RequestValidationError` | `422` + field-level details |
| `integrity_error_handler` | SQLAlchemy `IntegrityError` | `409` — duplicate/constraint |
| `sqlalchemy_exception_handler` | SQLAlchemy `SQLAlchemyError` | `500` — generic DB error |
| `redis_exception_handler` | `RedisError` | `503` — cache unavailable |
| `generic_exception_handler` | `Exception` (safety net) | `500` — unhandled fallback |

---

## 📁 Project Structure

```
E-Commerce/
├── app/
│   ├── main.py                         # App entry + router registration + error handlers
│   ├── api/
│   │   ├── dependencies.py             # get_current_user, require_roles, token chain
│   │   └── v1/
│   │       ├── auth.py                 # Register, login, refresh, verify, reset
│   │       ├── products.py             # Catalog CRUD & categories
│   │       ├── cart.py                 # Cart management (add, update, remove)
│   │       ├── order.py                # Checkout, verify-payment, cancel
│   │       ├── address.py              # Address book with soft-delete
│   │       ├── users.py                # User profile & order history
│   │       ├── admin.py                # Admin — products, orders, state machine
│   │       ├── coupon.py               # Coupon apply/remove + admin CRUD
│   │       ├── inventory.py            # Inventory admin (restock, adjust, alerts)
│   │       └── webhooks.py             # Razorpay webhook receiver
│   ├── core/
│   │   ├── config.py                   # Pydantic settings (env-driven)
│   │   ├── security.py                 # JWT (access, refresh, reset, verify tokens)
│   │   ├── redis.py                    # Rate limiting utility
│   │   ├── exceptions.py               # 20+ domain exception classes
│   │   ├── error_handlers.py           # 6 global exception handlers
│   │   └── logging_config.py           # Structured logging
│   ├── db/
│   │   ├── session.py                  # Async session factory
│   │   └── models/
│   │       ├── user.py                 # User + password_changed_at
│   │       ├── product.py              # Product + stock + thresholds
│   │       ├── cart.py                 # Cart + CartItem + subtotal
│   │       ├── order.py                # Order + OrderItem + status enum
│   │       ├── transaction.py          # Razorpay transaction record
│   │       ├── address.py              # Shipping address + soft-delete
│   │       ├── coupon.py               # Coupon + CouponUsage + DiscountType
│   │       ├── inventory.py            # StockMovement + StockMovementType
│   │       └── webhook_event.py        # Webhook audit log
│   ├── schemas/                        # Pydantic v2 request/response models
│   ├── services/
│   │   ├── order_service.py            # Checkout, verify, cancel, state machine
│   │   ├── coupon_service.py           # Validate, apply, use-in-checkout, rollback
│   │   ├── inventory_service.py        # Stock movements, adjust, restock, alerts
│   │   ├── webhook_service.py          # HMAC verify, event routing, idempotency
│   │   └── ...                         # Auth, cart, product services
│   ├── validators/                     # Reusable field-level validators
│   ├── utils/
│   │   └── email.py                    # FastAPI-Mail background sender
│   └── worker/
│       ├── celery_app.py               # Celery instance (Redis broker + backend)
│       └── tasks.py                    # send_invoice_email (HTML, retry ×3)
├── alembic/                            # Database migration scripts
├── backend/
│   └── docker-compose.yml              # PostgreSQL + Redis + API + Celery
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

---

## 🔗 API Reference

<details>
<summary><b>🔐 Auth</b> — <code>/auth</code> — Registration, login, token management</summary>

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `POST` | `/auth/register` | — | Register + send verification email |
| `GET` | `/auth/verify` | — | Activate account via email token |
| `POST` | `/auth/resend-verification` | — | Resend email (2-min Redis cooldown) |
| `POST` | `/auth/login` | — | Returns access + refresh token pair |
| `POST` | `/auth/refresh` | — | Rotate refresh token (theft detection) |
| `POST` | `/auth/logout` | Bearer | Blacklist access token |
| `POST` | `/auth/forgot-password` | — | Trigger reset (generic response) |
| `POST` | `/auth/reset-password` | — | Reset + invalidate all sessions |

</details>

<details>
<summary><b>👤 Users</b> — <code>/api/v1/users</code> — Profile & history</summary>

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/api/v1/users/me` | Bearer | Get own profile |
| `PATCH` | `/api/v1/users/me` | Bearer | Update name, email, phone |
| `GET` | `/api/v1/users/me/orders` | Bearer | Order history (paginated) |

</details>

<details>
<summary><b>📦 Catalog</b> — <code>/api/v1/products</code> — Products & categories</summary>

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `POST` | `/api/v1/products/categories` | Public | Create category |
| `GET` | `/api/v1/products/categories` | Public | List categories |
| `GET` | `/api/v1/products/` | Public | List active products (paginated) |
| `GET` | `/api/v1/products/{id}` | Public | Product detail |
| `POST` | `/api/v1/products/` | Public | Create product |
| `DELETE` | `/api/v1/products/{id}` | Public | Soft-delete product |

</details>

<details>
<summary><b>🛒 Cart</b> — <code>/api/v1/cart</code> — Cart management</summary>

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/api/v1/cart/` | Bearer | View cart (auto-creates if missing) |
| `POST` | `/api/v1/cart/items` | Bearer | Add item (stock validated) |
| `PUT` | `/api/v1/cart/items/{id}` | Bearer | Set quantity |
| `PATCH` | `/api/v1/cart/items/{id}/decrease` | Bearer | Decrease by 1 (auto-removes at 0) |
| `DELETE` | `/api/v1/cart/items/{id}` | Bearer | Remove item |
| `DELETE` | `/api/v1/cart/` | Bearer | Clear entire cart |

</details>

<details>
<summary><b>💳 Orders</b> — <code>/api/v1/orders</code> — Checkout & payments</summary>

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `POST` | `/api/v1/orders/checkout` | Bearer | Create Razorpay order + DB order (atomic) |
| `POST` | `/api/v1/orders/verify-payment` | Bearer | Verify signature → mark PAID |
| `GET` | `/api/v1/orders/` | Bearer | List user's paid orders |
| `GET` | `/api/v1/orders/{id}` | Bearer | Order detail |
| `PATCH` | `/api/v1/orders/{id}/cancel` | Bearer | Cancel + stock + coupon rollback |

</details>

<details>
<summary><b>🎟️ Coupons</b> — User & Admin coupon operations</summary>

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `POST` | `/api/v1/coupons/cart/apply-coupon` | Bearer | Apply coupon to cart |
| `DELETE` | `/api/v1/coupons/cart/remove-coupon` | Bearer | Remove coupon from cart |
| `POST` | `/api/v1/admin/coupons` | Admin | Create coupon |
| `GET` | `/api/v1/admin/coupons` | Admin | List coupons (filterable) |
| `GET` | `/api/v1/admin/coupons/{code}` | Admin | Get coupon by code |
| `PATCH` | `/api/v1/admin/coupons/{code}` | Admin | Partial update |
| `PATCH` | `/api/v1/admin/coupons/{code}/deactivate` | Admin | Deactivate coupon |

</details>

<details>
<summary><b>🛠️ Admin</b> — <code>/api/v1/admin</code> — Product & order management</summary>

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `POST` | `/api/v1/admin/products` | Admin | Create product |
| `GET` | `/api/v1/admin/products` | Admin | List all (incl. soft-deleted) |
| `PATCH` | `/api/v1/admin/products/{id}` | Admin | Partial update |
| `DELETE` | `/api/v1/admin/products/{id}` | Admin | Soft-delete |
| `GET` | `/api/v1/admin/orders` | Admin | List all orders (status filter) |
| `PATCH` | `/api/v1/admin/orders/{id}/status` | Admin | State-machine validated transition |

</details>

<details>
<summary><b>📊 Inventory</b> — <code>/api/v1/admin/inventory</code> — Stock management</summary>

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/admin/inventory/low-stock` | Admin | Products below threshold |
| `GET` | `/admin/inventory/reorder-alerts` | Admin | Products at/below reorder point |
| `GET` | `/admin/inventory/report` | Admin | Aggregated stock summary |
| `GET` | `/admin/inventory/{id}/movements` | Admin | Movement history (filterable) |
| `POST` | `/admin/inventory/{id}/adjust` | Admin | ± stock delta with reason |
| `POST` | `/admin/inventory/{id}/restock` | Admin | Add positive stock |
| `PATCH` | `/admin/inventory/{id}/thresholds` | Admin | Update alert thresholds |

</details>

<details>
<summary><b>📍 Addresses & Webhooks</b></summary>

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/api/v1/addresses/` | Bearer | List addresses |
| `POST` | `/api/v1/addresses/` | Bearer | Add address (first = auto-default) |
| `PATCH` | `/api/v1/addresses/{id}` | Bearer | Update |
| `PATCH` | `/api/v1/addresses/{id}/default` | Bearer | Set as default (atomic) |
| `DELETE` | `/api/v1/addresses/{id}` | Bearer | Soft-delete |
| `POST` | `/api/v1/webhooks/razorpay` | HMAC | Receive Razorpay payment events |

</details>

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Git

### 1. Clone & Configure

```bash
git clone https://github.com/Vishwam401/E-commerce.git
cd E-commerce
```

Create `.env.docker` in the project root:

```env
# ──── Database ────
DATABASE_URL=postgresql+asyncpg://postgres:vish@db:5432/ecommerce_db

# ──── JWT ────
SECRET_KEY=your_super_secret_key_min_32_chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ──── Redis ────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# ──── Email (Gmail SMTP) ────
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_FROM=your_email@gmail.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_STARTTLS=True
MAIL_SSL_TLS=False
EMAIL_VERIFY_BASE_URL=http://localhost:8001

# ──── Razorpay ────
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_SECRET_KEY=your_razorpay_secret
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret
```

### 2. Launch

```bash
cd backend
docker compose up --build -d
```

### 3. Run Migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Access

| Interface | URL |
|:---|:---|
| API Root | [`http://localhost:8001`](http://localhost:8001) |
| Swagger UI | [`http://localhost:8001/docs`](http://localhost:8001/docs) |
| ReDoc | [`http://localhost:8001/redoc`](http://localhost:8001/redoc) |

---

## 🛠 Tech Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Framework** | FastAPI 0.135 | Async REST API with auto-docs |
| **Language** | Python 3.11+ | Type hints, async/await |
| **Database** | PostgreSQL 15 | Primary data store (via asyncpg) |
| **ORM** | SQLAlchemy 2.0 | Fully async, mapped columns |
| **Migrations** | Alembic | Schema versioning |
| **Cache** | Redis Alpine | Token blacklist, rate limits, Celery broker |
| **Auth** | Argon2 + JWT | Hashing (passlib) + python-jose tokens |
| **Email** | smtplib (Celery) | Synchronous SMTP in worker (async-safe) |
| **Payments** | Razorpay SDK | Live order creation + signature verify |
| **Webhooks** | HMAC-SHA256 | Timing-attack safe via `compare_digest` |
| **Task Queue** | Celery | Redis broker + backend, auto-retry |
| **Validation** | Pydantic v2 | Request/response schemas |
| **Containers** | Docker Compose | PostgreSQL + Redis + API + Celery worker |

---

## ✅ Smoke Test Checklist

```
 1. POST  /auth/register                          → verification email sent
 2. GET   /auth/verify?token=...                  → account activated
 3. POST  /auth/login                             → save access + refresh tokens
 4. GET   /api/v1/users/me                        → profile returned
 5. POST  /api/v1/addresses/                      → add shipping address
 6. POST  /api/v1/cart/items                      → add products to cart
 7. POST  /api/v1/admin/coupons          (admin)  → create coupon
 8. POST  /api/v1/coupons/cart/apply-coupon       → attach coupon to cart
 9. POST  /api/v1/orders/checkout                 → receive razorpay_order_id
10. POST  /api/v1/orders/verify-payment           → mark PAID, invoice queued
11. POST  /api/v1/webhooks/razorpay               → test with valid HMAC header
12. PATCH /api/v1/orders/{id}/cancel              → stock + coupon rolled back
13. PATCH /api/v1/admin/orders/{id}/status        → test state machine transitions
14. GET   /api/v1/admin/inventory/report          → stock summary
15. POST  /api/v1/admin/inventory/{id}/restock    → test RESTOCK movement
16. 6+ bad logins                                 → 429 → wait 60s → 200
```

---

## 🗺 Roadmap

- [x] JWT auth with email verification, refresh rotation & theft detection
- [x] Redis token blacklist + dual-layer rate limiting
- [x] Full cart & order lifecycle with atomic stock management
- [x] Razorpay live payment integration + signature verification
- [x] Server-side webhook handler with audit log
- [x] Celery async invoice email (HTML, auto-retry)
- [x] Order state machine with validated transitions
- [x] Order cancellation with atomic stock + coupon rollback
- [x] Coupon engine (%, flat, caps, per-user limits, race-condition safe)
- [x] Inventory management — stock movement audit, low-stock alerts, reorder points
- [x] Admin panel — products, orders, coupons, inventory
- [x] Custom exception hierarchy (20+ classes) with structured global handlers
- [ ] Redis-backed cart caching
- [ ] Sentry error tracking integration
- [ ] Product reviews & ratings
- [ ] Wishlist / saved items

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/Vishwam401">Vishwam401</a></sub>
</p>
