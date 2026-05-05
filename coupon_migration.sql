-- Create Enum Type
CREATE TYPE discounttype AS ENUM ('flat', 'percentage');

-- 1. CREATE COUPONS TABLE
CREATE TABLE coupons (
    id UUID NOT NULL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    discount_type discounttype NOT NULL,
    discount_value NUMERIC(10,2) NOT NULL,
    min_order_value NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    max_discount_cap NUMERIC(10,2),
    max_total_uses INTEGER NOT NULL DEFAULT 1,
    max_uses_per_user INTEGER NOT NULL DEFAULT 1,
    total_used_count INTEGER NOT NULL DEFAULT 0,
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX ix_coupons_code ON coupons(code);

-- 2. CREATE COUPON_USAGES TABLE
CREATE TABLE coupon_usages (
    id UUID NOT NULL PRIMARY KEY,
    coupon_id UUID NOT NULL REFERENCES coupons(id)ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    used_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE(coupon_id, user_id, order_id)
);

CREATE INDEX ix_coupon_usages_coupon_id ON coupon_usages(coupon_id);
CREATE INDEX ix_coupon_usages_user_id ON coupon_usages(user_id);

-- 3. ADD COUPON COLUMNS TO CARTS TABLE
ALTER TABLE carts ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(50);
ALTER TABLE carts ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00;

-- 4. ADD COUPON COLUMNS TO ORDERS TABLE
ALTER TABLE orders ADD COLUMN IF NOT EXISTS coupon_code_snapshot VARCHAR(50);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00;

