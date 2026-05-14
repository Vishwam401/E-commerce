# 🎯 COUPON SYSTEM FLOW DIAGRAM

## USER FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER COUPON FLOW                             │
└─────────────────────────────────────────────────────────────────┘

    1. BROWSE & CART
    ═══════════════
    
    User Views Products
           │
           ├─ GET /api/v1/products
           └─ Response: [Product 1, Product 2, ...]
    
    Add to Cart
           │
           ├─ POST /api/v1/cart/items
           │  {product_id, quantity}
           │
           ├─ DB Update: Carts, CartItems
           └─ Response: Cart with items


    2. APPLY COUPON
    ═════════════
    
    User enters coupon code
           │
           ├─ POST /api/v1/cart/apply-coupon
           │  {code}
           │
           └─ VALIDATION CHAIN:
              ├─ Does coupon exist?              → 404 if NO
              ├─ Is coupon active?               → 400 if NO
              ├─ Is within valid dates?          → 400 if NO
              ├─ Is it already applied?          → 400 if YES
              ├─ Cart total ≥ min_order?         → 400 if NO
              ├─ Global usage limit hit?         → 400 if YES
              ├─ User usage limit hit?           → 400 if YES
              └─ All good! ✓
    
    Calculate Discount
           │
           ├─ If FLAT: discount = min(value, cart_total)
           │
           ├─ If PERCENTAGE:
           │  calc = cart_total * (value / 100)
           │  if cap: calc = min(calc, cap)
           │  discount = min(calc, cart_total)
           │
           └─ Round to 2 decimals: ROUND_HALF_UP
    
    Update Cart
           │
           ├─ DB Update:
           │  ├─ carts.coupon_code = normalized_code
           │  ├─ carts.discount_amount = calculated_discount
           │  └─ COMMIT
           │
           └─ Response:
              {
                "coupon_code": "FLAT100",
                "discount_amount": 100.00,
                "original_total": 750.00,
                "final_total": 650.00
              }


    3. CHECKOUT (CRITICAL)
    ══════════════════════
    
    User initiates checkout
           │
           ├─ POST /api/v1/orders/checkout
           │  {address_id}
           │
           └─ ACQUIRE LOCK:
              ├─ SELECT Coupon WITH FOR_UPDATE (block others)
              │
              ├─ RE-VALIDATE:
              │  ├─ Coupon still exists?
              │  ├─ Still active?
              │  ├─ Still within date range?
              │  ├─ Global limit not hit?
              │  └─ User limit not exceeded?
              │
              ├─ ALL GOOD: Lock held, no race possible
              └─ MUTATE (inside transaction):
                 ├─ coupon.total_used_count += 1
                 ├─ Create CouponUsage record
                 ├─ Update Order snapshots:
                 │  ├─ coupon_code_snapshot
                 │  └─ discount_amount
                 ├─ COMMIT
                 └─ UNLOCK (transaction end)
    
    
    4. ORDER CREATED
    ═══════════════
    Response:
    {
      "order": {
        "id": "order-uuid",
        "total_price": 785.00,
        "discount_amount": 100.00,
        "coupon_code_snapshot": "FLAT100",
        "status": "pending"
      },
      "payment_details": {
        "razorpay_order_id": "order_...",
        "amount": 78500
      }
    }


    5. NEXT TIME (PER-USER LIMIT)
    ═════════════════════════════
    User tries to apply same coupon again
           │
           ├─ POST /api/v1/cart/apply-coupon
           │  {code: "FLAT100"}
           │
           └─ VALIDATION:
              ├─ Check CouponUsage.count(coupon_id, user_id)
              ├─ Count: 1 (from last checkout)
              ├─ Limit: 1 (max_uses_per_user)
              ├─ COUNT >= LIMIT → TRUE
              └─ ERROR ❌: "You have already used coupon 'FLAT100' maximum times."
```

---

## ADMIN FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                    ADMIN COUPON FLOW                             │
└─────────────────────────────────────────────────────────────────┘

    1. CREATE COUPON
    ═══════════════
    
    Admin submits form
           │
           ├─ POST /api/v1/admin/coupons
           │  {
           │    "code": "FLAT100",
           │    "discount_type": "flat",
           │    "discount_value": 100.00,
           │    "min_order_value": 500.00,
           │    "max_total_uses": 10,
           │    "max_uses_per_user": 2,
           │    "valid_from": "2026-05-01T00:00:00Z",
           │    "valid_until": "2026-05-31T23:59:59Z",
           │    "is_active": true
           │  }
           │
           └─ VALIDATION (Pydantic):
              ├─ Code length: 1-50 chars
              ├─ Code normalized: strip().upper()
              ├─ Discount value > 0
              ├─ If percentage: 0-100%
              ├─ If percentage + cap: cap > 0
              ├─ valid_until > valid_from
              ├─ Check code doesn't exist (unique)
              └─ ALL GOOD → CREATE
    
    Insert into DB
           │
           ├─ DB Insert:
           │  ├─ coupons table
           │  ├─ auto id (UUID)
           │  ├─ auto created_at
           │  └─ total_used_count = 0
           │
           └─ Response: 201 Created
              {
                "id": "uuid",
                "code": "FLAT100",
                ...
                "created_at": "2026-05-05T12:00:00+00:00"
              }


    2. LIST COUPONS
    ══════════════
    
    GET /api/v1/admin/coupons?active_only=true&page=1&page_size=20
           │
           └─ Query filters applied:
              ├─ WHERE is_active = true
              ├─ ORDER BY created_at DESC
              ├─ OFFSET 0
              ├─ LIMIT 20
              └─ COUNT total records
    
    Response: 200 OK
    {
      "items": [...],
      "total": 5,
      "page": 1,
      "page_size": 20
    }


    3. SEARCH COUPONS
    ════════════════
    
    GET /api/v1/admin/coupons?search=FLAT
           │
           └─ Query:
              ├─ WHERE code ILIKE '%FLAT%'
              └─ Case-insensitive search
    
    Response: [Coupon: FLAT100, FLAT50, ...]


    4. UPDATE COUPON
    ════════════════
    
    PATCH /api/v1/admin/coupons/FLAT100
    {
      "discount_value": 150.00,
      "max_total_uses": 15
    }
           │
           └─ VALIDATION:
              ├─ Only update provided fields
              ├─ If code changed: check uniqueness
              ├─ Re-validate everything
              └─ UPDATE & COMMIT
    
    Response: 200 OK (updated coupon)


    5. DEACTIVATE COUPON
    ═══════════════════
    
    PATCH /api/v1/admin/coupons/FLAT100/deactivate
           │
           └─ Soft delete:
              ├─ Set is_active = false
              ├─ COMMIT
              └─ USERS CANNOT APPLY NOW
    
    When user tries to apply:
           │
           └─ Validation check: is_active?
              ├─ FALSE → ERROR ❌
              └─ "Coupon 'FLAT100' is Inactive"


    6. MONITOR USAGE
    ════════════════
    
    GET /api/v1/admin/coupons/FLAT100
           │
           └─ Response includes:
              {
                ...
                "total_used_count": 5,
                "max_total_uses": 10,        ← 5/10 used
                ...
              }
    
    Query CouponUsage for details:
           │
           └─ Check coupon_usages table:
              ├─ coupon_id = "..."
              ├─ user_id = "..."
              ├─ order_id = "..." (or NULL)
              └─ used_at = "2026-05-05T..."
```

---

## DATABASE RELATIONSHIPS

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA MODEL                                   │
└─────────────────────────────────────────────────────────────────┘


    ┌────────────┐
    │  COUPONS   │
    ├────────────┤
    │ id (PK)    │───────────┐
    │ code (UQ)  │           │
    │ discount   │           │ 1:N
    │ valid_from │           │
    │ valid_...  │           │
    │ is_active  │           │
    │ total_used │           │
    └────────────┘           │
                             │
                    ┌────────────────┐
                    │ COUPON_USAGES  │
                    ├────────────────┤
                    │ id (PK)        │
                    │ coupon_id (FK) │◄──┘
                    │ user_id (FK)   │──────┐
                    │ order_id (FK)  │──┐   │
                    │ used_at        │  │   │
                    └────────────────┘  │   │
                         │              │   │
                         │              │   │
                    ┌────┴────┐    ┌────┴────┐
                    │ ORDERS   │    │ USERS   │
                    ├──────────┤    ├─────────┤
                    │ id  (PK) │    │ id (PK) │
    ┌──────────────→│ user_id  │    │ ...     │
    │               │ coupon_  │    └─────────┘
    │               │   code_  │
    │               │   snapshot
    │               │ discount_│
    │               │   amount │
    │               └──────────┘
    │                    │
    │               1:N  │
    │                    │
    │          ┌─────────┴─────────┐
    │          │   ORDER_ITEMS     │
    │          ├───────────────────┤
    │          │ order_id (FK)     │
    └──────────│ product_id (FK)   │
               │ quantity          │
               │ price_at_purchase │
               └───────────────────┘


    ┌────────────┐
    │   CARTS    │
    ├────────────┤
    │ id (PK)    │
    │ user_id    │
    │ coupon_    │ ← Applied coupon code
    │   code     │
    │ discount_  │ ← Calculated discount
    │   amount   │
    └────────────┘
         │
         │ 1:N
         │
    ┌────┴─────────┐
    │  CART_ITEMS  │
    ├──────────────┤
    │ cart_id (FK) │
    │ product_id   │
    │ quantity     │
    └──────────────┘


KEY FLOWS:
═════════

Apply Coupon:
    CARTS.coupon_code ← code
    CARTS.discount_amount ← calculated

Checkout (with lock):
    FOR UPDATE locks COUPONS row
    ├─ COUPONS.total_used_count += 1
    ├─ INSERT COUPON_USAGES record
    ├─ ORDERS.coupon_code_snapshot ← snapshot
    └─ ORDERS.discount_amount ← snapshot

Audit Trail:
    All COUPON_USAGES persisted forever
    ├─ Preserves history even if ORDERS deleted
    ├─ Per-user usage calculated from here
    └─ Admin can track all discount usage
```

---

## ERROR SCENARIOS

```
┌─────────────────────────────────────────────────────────────────┐
│                 ERROR HANDLING FLOWCHART                         │
└─────────────────────────────────────────────────────────────────┘


POST /api/v1/cart/apply-coupon {code: "FLAT100"}
│
├─ Normalize code → "FLAT100"
│
├─ Query Coupon by code
│  ├─ NOT found            → 404: "not found"
│  └─ Found               → Continue
│
├─ Is coupon active?
│  ├─ NO                   → 400: "is Inactive"
│  └─ YES                  → Continue
│
├─ Current time in valid range?
│  ├─ Too early             → 400: "not active yet"
│  ├─ Too late              → 400: "has expired"
│  └─ Valid range           → Continue
│
├─ Is coupon already applied?
│  ├─ YES                   → 400: "already applied"
│  └─ NO                    → Continue
│
├─ Cart total ≥ min_order_value?
│  ├─ NO                    → 400: "Minimum order of ₹X required..."
│  └─ YES                   → Continue
│
├─ Global usage limit?
│  ├─ Hit (count >= max)    → 400: "usage limit reached"
│  └─ Available             → Continue
│
├─ Per-user usage limit?
│  ├─ Hit (count >= max)    → 400: "You have already used... maximum"
│  └─ Available             → Continue
│
├─ Calculate discount
│  ├─ Flat: amount = min(value, cart_total)
│  └─ Percentage: amount = min(% calc, cap, cart_total)
│
├─ Update cart
│  ├─ DB error             → 500: "Database error"
│  └─ Success              → 200: ApplyCouponResponse
│
└─ Response
   {
     "coupon_code": "FLAT100",
     "discount_amount": 100.00,
     "original_total": 750.00,
     "final_total": 650.00
   }
```

---

## DECIMAL CALCULATION EXAMPLE

```
┌─────────────────────────────────────────────────────────────────┐
│            MONEY CALCULATION IN CHECKOUT                         │
└─────────────────────────────────────────────────────────────────┘


INPUT:
  Cart Items: [Item1: ₹500, Item2: ₹250]
  Coupon: SAVE20 (20% off, max cap ₹150)
  
CALCULATE:
  
  1. Subtotal
     ┌─ Item1 qty: 1 × ₹500 = ₹500
     ├─ Item2 qty: 1 × ₹250 = ₹250
     └─ Subtotal = ₹750
  
  2. Tax (18%)
     └─ Tax = ₹750 × 0.18 = ₹135.00
  
  3. Shipping
     └─ Subtotal ≥ ₹500? YES → Free shipping
  
  4. Discount
     Raw = ₹750 × (20% / 100) = ₹150
     Capped = min(₹150, ₹150 cap) = ₹150
     Final = min(₹150, ₹750) = ₹150.00 ✓
  
  5. Total
     Grand Total = Subtotal + Tax + Shipping - Discount
                 = ₹750 + ₹135 + ₹0 - ₹150
                 = ₹735.00
  
Razorpay Amount (in Paise):
  ₹735.00 × 100 = 73,500 paise


OUTPUT IN ORDER:
{
  "subtotal_price": 750.00,
  "tax_price": 135.00,
  "shipping_price": 0.00,
  "discount_amount": 150.00,
  "coupon_code_snapshot": "SAVE20",
  "total_price": 735.00
}


VALIDATION:
  total_price = subtotal + tax + shipping - discount
  735 = 750 + 135 + 0 - 150 ✓
```

---

## QUICK REFERENCE

```
┌─────────────────────────────────────────────────────────────────┐
│                ENDPOINTS AT A GLANCE                             │
└─────────────────────────────────────────────────────────────────┘

USER ENDPOINTS:
  POST   /api/v1/cart/apply-coupon               (200/400/404)
  DELETE /api/v1/cart/remove-coupon              (200)

ADMIN ENDPOINTS:
  POST   /api/v1/admin/coupons                   (201/400)
  GET    /api/v1/admin/coupons                   (200)
  GET    /api/v1/admin/coupons/{code}            (200/404)
  PATCH  /api/v1/admin/coupons/{code}            (200/400/404)
  PATCH  /api/v1/admin/coupons/{code}/deactivate (200/404)


DISCOUNT TYPES:
  • flat       → Fixed amount off
  • percentage → Percentage discount with optional cap


STATUS CODES:
  • 200 ✓ Success
  • 201 ✓ Created
  • 400 ✗ Bad request (validation failed)
  • 404 ✗ Not found (coupon/address doesn't exist)
  • 500 ✗ Server error


COMMON VALIDATIONS:
  • Code: 1-50 chars, UPPERCASE internally
  • Discount: > 0
  • Percentage: 0-100%
  • Min order: ≥ 0
  • Dates: valid_until > valid_from
  • Per-user: > 0
  • Total uses: > 0
```

🎯 Ready to test! Start with COUPON_QUICK_REFERENCE.md

