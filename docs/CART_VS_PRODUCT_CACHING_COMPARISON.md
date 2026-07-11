# Cart Caching vs Product Caching — Side-by-Side Comparison

> **Purpose**: Ye document dono caching implementations (Cart aur Product) ko compare karta hai — same project mein, do alag Redis data structures, do alag invalidation strategies. Interview mein "tumne caching kaise implement ki, dono jagah same tareeke se ki?" — iska jawab yahi hai.
>
> **Core message jo yaad rakhni hai**: **Dono Cache-Aside pattern follow karte hain** (high-level same soch), **lekin implementation details bilkul alag hain** kyunki data ka nature alag hai. Ye distinction hi senior-level understanding dikhata hai.

---

## Table of Contents

1. [Common Ground — Dono mein kya same hai](#1-common-ground)
2. [Core Difference — Data Structure Choice](#2-core-difference-data-structure)
3. [Side-by-Side: Read Path](#3-side-by-side-read-path)
4. [Side-by-Side: Write Path](#4-side-by-side-write-path)
5. [Side-by-Side: Invalidation Strategy](#5-side-by-side-invalidation-strategy)
6. [Key Design Decisions — Why Different Choices](#6-key-design-decisions)
7. [Interview-Ready Summary Table](#7-interview-ready-summary-table)
8. [Common Interview Questions + Answers](#8-interview-questions)

---

## 1. Common Ground

Dono services **ek hi pattern** follow karte hain: **Cache-Aside** (jo Section A.1 mein `CART_CACHING_EXPLAINED.md` mein detail se cover kiya tha).

```
READ:  Cache check → HIT? return → MISS? DB se laao → cache mein daalo → return
WRITE: DB update karo → cache ko invalidate/update karo
```

Dono files mein ye common patterns hain:

| Pattern | Cart mein | Product mein |
|---|---|---|
| Redis client access | `_get_redis()` helper | Direct `redis_client` import |
| Error handling | `try/except RedisError` har function mein | Same — `try/except RedisError` har function mein |
| Fail gracefully | Error aaye to `None`/`False` return, crash nahi | Same — `None` return, crash nahi |
| Logging | `logger.warning(f"[CART_CACHE] ...")` | `logger.warning(f"[PRODUCT_CACHE] ...")` |
| Key builder function | `_cart_key(user_id)` | `_product_key(product_id)` |
| TTL from config | `settings.CART_CACHE_TTL` | `settings.PRODUCT_CACHE_TTL` |
| DB never stores prices/sensitive data in cache blindly | Price hamesha DB se (cart mein sirf qty) | Product cache mein khud product data hai (yahan tradeoff hai — Section 6 mein explain) |

**Bottom line**: Agar tumhe kisi ko "cache-aside kaise likhte ho" samjhana ho, structure same hai — bas andar ka data aur uski Redis representation alag hai.

---

## 2. Core Difference — Data Structure Choice

Yahi sabse important interview point hai. **Redis mein 2 alag data types use hue hain, aur ye choice deliberate hai — random nahi.**

### Cart → Redis HASH

```
cart:{user_id}  →  HASH { product_id: quantity, product_id: quantity, ... }
```

```python
await redis.hgetall(_cart_key(user_id))
await redis.eval(ADD_ITEM_SCRIPT, 1, ...)   # Lua script HSET/HGET use karta hai
```

**Kyun Hash?**
- Cart mein **multiple fields** hain jo **independently update** hote hain (ek product ki qty badhao, doosre ko chhuo mat)
- Hash mein `HSET key field value` se **sirf ek field** update hoti hai — poora cart rewrite nahi karna padta
- Cart ek **structured object** hai (product_id → qty mapping) — Hash bilkul natural fit hai

### Product → Redis STRING (JSON serialized)

```
product:{product_id}         →  STRING  '{"id": "...", "name": "...", "price": 999, ...}'
products:list:v1:skip=0:limit=20  →  STRING  '[{...}, {...}, {...}]'
```

```python
raw_data = await redis_client.get(_product_key(product_id))
return json.loads(raw_data)

json_data = json.dumps(product_data)
await redis_client.setex(name=..., time=PRODUCT_TTL, value=json_data)
```

**Kyun String + JSON?**
- Product data **ek single unit** hai jo **poora ka poora** replace hota hai (price badla to poora object dobara cache karo, partial update ka koi use case nahi)
- Product mein **nested/complex fields** hain (name, price, description, attributes dict, category) — Hash mein har field alag se rakhna overkill hai jab ek saath hi consume hota hai
- JSON string simplest hai jab **read pattern** = "poora object chahiye ek saath", **write pattern** = "poora object replace karo"

### Analogy samjho

```
Cart = ek grocery list jisme items add/remove hote rehte hain
       → har item ko independently touch karna padta hai
       → HASH (like a dictionary you can edit field by field)

Product = ek product ka pura "profile card"
       → jab bhi dikhana hai, pura card dikhana hai
       → jab bhi badalna hai, pura card badal jaata hai
       → STRING with JSON (like a printed card — poora reprint karo, ek line edit nahi kar sakte)
```

---

## 3. Side-by-Side: Read Path

### Cart Read (`get_cart_from_cache`)

```python
async def get_cart_from_cache(user_id: uuid.UUID) -> Optional[dict[str, int]]:
    redis = _get_redis()
    try:
        raw = await redis.hgetall(_cart_key(user_id))
        if not raw:
            return None
        return {pid: int(qty) for pid, qty in raw.items()}
    except RedisError as exc:
        logger.warning(f"[CART_CACHE] Read failed: user={user_id}: {exc}")
        return None
```

### Product Read (`get_product_from_cache`)

```python
async def get_product_from_cache(product_id: uuid.UUID | str) -> Optional[Dict[str, Any]]:
    try:
        raw_data = await redis_client.get(_product_key(product_id))
        if not raw_data:
            return None
        return json.loads(raw_data)
    except RedisError as exc:
        logger.warning(f"[PRODUCT_CACHE] Read failed: product={product_id}: {exc}")
        return None
    except json.JSONDecodeError:
        logger.warning(f"[PRODUCT_CACHE] JSON decode failed for product={product_id}")
        return None
```

### Difference table

| Aspect | Cart | Product |
|---|---|---|
| Redis command | `HGETALL` (hash ke saare fields) | `GET` (single string value) |
| Deserialization | Manual dict comprehension (`{pid: int(qty)...}`) — kyunki Redis Hash values hamesha strings hoti hain, int conversion manual | `json.loads()` — JSON parser khud sab types (int, str, dict, list) handle kar leta hai |
| Extra error case | Sirf `RedisError` | `RedisError` **+ `json.JSONDecodeError`** (JSON corrupt ho sakta hai, Hash mein ye risk nahi) |
| Return type | `dict[str, int]` (product_id → qty) | `Dict[str, Any]` (poora product object) |

**Interview point**: JSON serialization ek **extra failure mode** introduce karta hai (`JSONDecodeError`) jo Hash approach mein nahi hota. Ye tradeoff hai flexibility (koi bhi complex object store kar sakte ho) vs simplicity.

---

## 4. Side-by-Side: Write Path

### Cart Write (`add_item_to_cache`) — Lua Script

```python
ADD_ITEM_SCRIPT = """
local current = redis.call('HGET', KEYS[1], ARGV[1])
if current then
    local new_qty = tonumber(current) + tonumber(ARGV[2])
    redis.call('HSET', KEYS[1], ARGV[1], new_qty)
else
    redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
end
redis.call('EXPIRE', KEYS[1], ARGV[3])
return redis.call('HGET', KEYS[1], ARGV[1])
"""

async def add_item_to_cache(user_id, product_id, quantity) -> Optional[int]:
    redis = _get_redis()
    try:
        result = await redis.eval(
            ADD_ITEM_SCRIPT, 1,
            _cart_key(user_id), str(product_id), str(quantity), str(CART_TTL),
        )
        await _refresh_meta_ttl(redis, user_id)
        return int(result) if result is not None else None
    except RedisError as exc:
        ...
```

### Product Write (`set_product_in_cache`) — Simple SETEX

```python
async def set_product_in_cache(product_id: uuid.UUID | str, product_data: Dict[str, Any]) -> None:
    try:
        json_data = json.dumps(product_data)
        await redis_client.setex(
            name=_product_key(product_id),
            time=PRODUCT_TTL,
            value=json_data
        )
    except RedisError as exc:
        ...
```

### Difference table

| Aspect | Cart | Product |
|---|---|---|
| Atomicity mechanism | **Lua script** (multi-step logic atomic banane ke liye) | **Single `SETEX` command** (already atomic — koi multi-step logic nahi) |
| Kyun Lua chahiye/nahi chahiye | "Read current qty → add → write" — ye 3 steps hain. Bina Lua, 2 concurrent requests race condition create kar sakti hain (Section A.2 dekh cart doc mein) | "Poora object replace karo" — ye already single atomic operation hai. Koi read-modify-write nahi ho raha, isliye Lua ki zarurat nahi |
| Increment logic | HAAN — qty ADD hoti hai (2 + 3 = 5) | NAHI — product data REPLACE hota hai (purana gaya, naya aaya) |
| TTL setting | Alag `EXPIRE` command (Lua ke andar) | `SETEX` mein hi built-in (`time=PRODUCT_TTL` parameter) |

**Interview point — ye sabse important hai**: **Lua sirf tab chahiye jab multiple Redis operations ko "atomic unit" banana ho** (read-then-write races se bachne ke liye). Product cache mein sirf ek "set/replace" operation hai — atomicity already guaranteed hai by Redis itself (single command). Isliye Lua overkill hota product cache mein — **right tool for the right job**.

---

## 5. Side-by-Side: Invalidation Strategy

Ye sabse **interesting difference** hai — dono ka invalidation approach fundamentally alag hai.

### Cart — No "invalidation" concept, sirf direct mutation + TTL refresh

Cart mein "invalidate" jaisa kuch nahi hai (except `clear_cart_cache`). Kyun? Kyunki cart ka data khud hi cache mein "source of truth" hai (temporarily) — jab user item add/remove karta hai, seedha Redis update hota hai (`HSET`/`HDEL`), "purana cache delete karke fresh lao" wali baat nahi hai.

```python
async def clear_cart_cache(user_id: uuid.UUID) -> bool:
    """DEL cart + meta keys (idempotent). Called on clear/checkout."""
    redis = _get_redis()
    try:
        await redis.delete(_cart_key(user_id), _meta_key(user_id))
        return True
    ...
```

Sirf **checkout/clear** pe direct `DELETE` hota hai — ye bhi "invalidation" nahi hai, ye "cart khatam ho gaya" hai.

### Product — 2-Level Invalidation Strategy

#### Level 1: Single Product — Direct Delete

```python
async def invalidate_product_cache(product_id: uuid.UUID | str) -> None:
    """Delete a product from Redis."""
    try:
        await redis_client.delete(_product_key(product_id))
    ...
```

Simple hai — jab product update/delete ho, uski specific key delete kardo. Next read pe MISS hoga, fresh data aayega.

#### Level 2: Product List — Version Counter (NOT direct delete)

```python
async def invalidate_product_list_cache() -> None:
    """
    Invalidate all list cache pages by bumping the version number.
    Old keys are left alone — they expire naturally via TTL.
    """
    try:
        await redis_client.incr(LIST_VERSION_KEY)
    ...
```

**Ye alag kyun hai?** Single product ki **ek hi key** hoti hai (`product:{id}`) — delete karna trivial hai. Lekin list cache ki **N possible keys** ho sakti hain (`skip=0,limit=20`, `skip=20,limit=20`, `skip=40,limit=10`, ...) — kaunsi exact keys delete karein, pata nahi. Redis `KEYS pattern*` se sab dhoondh ke delete karna **slow aur production mein risky** hai (blocking operation, O(N)).

Isliye **version-counter trick**: sab list keys mein ek `v{N}` prefix hota hai. Invalidate karne ke liye sirf `N` ko `INCR` karo — O(1) operation. Purani keys "orphan" ho jaati hain, apni TTL pe khud expire ho jaati hain.

### Difference table

| Aspect | Cart | Product (single) | Product (list) |
|---|---|---|---|
| Invalidation mechanism | N/A — direct mutation | `DEL` specific key | `INCR` version counter |
| Number of cache keys per entity | 2 fixed keys per user (`cart:{id}`, `cart:meta:{id}`) | 1 fixed key per product | N dynamic keys (per skip/limit combo) |
| Complexity | Simple — mutate directly | Simple — delete 1 key | Clever — avoid deleting N unknown keys |
| Called from | N/A | `product_service.py` (create/update/delete), `inventory_service.py` (stock change) | Same call sites — bundled together |

---

## 6. Key Design Decisions — Why Different Choices

### Decision 1: Hash vs JSON String

| | Cart chose HASH | Product chose JSON STRING |
|---|---|---|
| Reasoning | Partial updates needed (qty of one item without touching others) | Whole-object replace needed (no partial update use case) |
| Tradeoff accepted | Manual type conversion (Hash values always strings) | Extra failure mode (JSON parse error) |

### Decision 2: Lua Script vs Plain Command

| | Cart chose Lua | Product chose plain SETEX |
|---|---|---|
| Reasoning | Read-modify-write needs atomicity across steps (race condition risk) | Single replace operation is already atomic |
| Tradeoff accepted | More complex code (embedded Lua), harder to debug | None — simpler is strictly better here |

### Decision 3: Direct Mutation vs Explicit Invalidation

| | Cart: direct mutation | Product: explicit invalidation |
|---|---|---|
| Reasoning | Cart data literally "lives" in Redis as source of truth (with async DB sync) | Product data's source of truth is always DB — Redis is purely a read-through cache |
| Tradeoff accepted | Requires background sync mechanism to keep DB eventually consistent | Slight staleness window between DB write and cache invalidation (usually microseconds, same request) |

### Decision 4: Fixed Keys vs Version-Counter Keys

| | Product (single): fixed key | Product (list): version-counter key |
|---|---| ---|
| Reasoning | Only 1 key per product — trivial to target and delete | Unbounded key combinations (any skip/limit pair) — can't enumerate and delete them all safely |
| Tradeoff accepted | None — straightforward | Old keys linger in memory until TTL (max 5 min) — acceptable staleness window |

---

## 7. Interview-Ready Summary Table

Agar interviewer bole "in dono caching implementations mein farak samjhao" — ye table seedha bol sakte ho:

| Dimension | Cart Caching | Product Caching |
|---|---|---|
| **Pattern** | Cache-Aside | Cache-Aside |
| **Redis data type** | Hash (`HSET`/`HGETALL`) | String + JSON (`SET`/`GET`) |
| **Why this type** | Need partial field updates | Need whole-object replace |
| **Atomicity tool** | Lua script (multi-step logic) | None needed (single command atomic) |
| **TTL** | 7 days, refreshed on every op | 5 min, set once on write |
| **Source of truth** | Redis (temporarily) + async synced to DB | Always DB — Redis is pure cache |
| **Invalidation** | Direct mutation (no separate invalidate step) | Explicit invalidate on write (DEL for single, version-bump for list) |
| **List/pagination handling** | N/A (cart has no pagination) | Version-counter pattern to avoid deleting unknown key sets |
| **Consistency model** | Eventual (Redis→DB via background task) | Read-through, always fresh within TTL window |
| **Failure mode** | Graceful fallback to DB on Redis error | Graceful fallback to DB on Redis error (same) |

---

## 8. Common Interview Questions + Answers

### Q1: "Dono jagah Redis use kiya, same tarike se kiya kya?"

**A**: Pattern same hai (Cache-Aside — check cache, miss pe DB, phir cache warm karo), lekin implementation data ke nature ke hisaab se alag hai. Cart mein Hash use kiya kyunki individual items independently update hote hain. Product mein JSON string use kiya kyunki poora object ek unit ki tarah replace hota hai.

### Q2: "Lua script kahan use kiya aur kahan nahi, kyun?"

**A**: Lua sirf cart mein use kiya, quantity increment karne ke liye — kyunki "read current value, add to it, write back" ek multi-step operation hai jo bina atomicity ke race condition create kar sakta hai (2 concurrent requests dono purani value padh ke apna-apna add kar dein, ek ka update kho jaaye). Product cache mein Lua nahi chahiye kyunki hum sirf "replace karo" kar rahe hain — single `SETEX` command khud atomic hai, extra locking ki zarurat nahi.

### Q3: "List/pagination cache invalidate kaise karte ho jab tumhe exact keys nahi pata?"

**A**: Version-counter pattern use kiya. Har cache key mein version number embed hai (`products:list:v1:...`). Invalidate karne ke liye sirf version ko `INCR` karte hain — ye O(1) hai. Purane version wale keys "unreachable" ho jaate hain (koi naya request unhe nahi dhundega), aur apni TTL khatam hone pe khud Redis se saaf ho jaate hain. Isse humein `KEYS pattern*` jaisa slow/blocking scan nahi karna padta jo production mein risky hota hai.

### Q4: "Cart ka data DB se kaise sync hota hai agar Redis hi source of truth hai?"

**A**: Background async task (`asyncio.create_task`) fire hota hai har cart mutation ke baad, jo Redis ki current state padh ke DB mein diff-apply karta hai (add/update/delete jo bhi change hua). User ko wait nahi karna padta — response turant Redis se mil jaata hai, DB eventual consistency follow karta hai.

### Q5: "Product cache mein Redis down ho jaye to kya hoga?"

**A**: Dono services mein same graceful-degradation pattern hai — `RedisError` ko catch karke `None`/`False` return karte hain, exception throw nahi karte. Calling code (`product_service.py`, `cart_service.py`) is `None` ko "cache miss" treat karta hai aur DB se seedha data laata hai. App crash nahi hota, bas thoda slow ho jaata hai jab tak Redis wapas na aaye.

### Q6: "TTL alag kyun rakha — cart 7 din, product 5 min?"

**A**: Cart data user-specific aur medium-term valuable hai (ek user apna cart hafte tak persist rakhna chahega). Product data **frequently changes** ho sakta hai (price update, stock change) aur **sabke liye shared** hai — chhoti TTL (5 min) staleness window ko minimize karta hai bina explicit invalidation ka zyada burden liye. Ye ek tradeoff hai — bahut chhoti TTL cache hit-rate ghatati hai, bahut badi TTL staleness risk badhati hai.

---

## Quick Reference — File-to-File Mapping

| Concept | Cart file/function | Product file/function |
|---|---|---|
| Read from cache | `cart_cache_service.get_cart_from_cache()` | `product_cache_service.get_product_from_cache()` / `get_product_list_from_cache()` |
| Write to cache | `cart_cache_service.add_item_to_cache()` (Lua) | `product_cache_service.set_product_in_cache()` / `set_product_list_in_cache()` |
| Invalidate | `clear_cart_cache()` (full delete on checkout) | `invalidate_product_cache()` (single) / `invalidate_product_list_cache()` (version bump) |
| Orchestration layer | `cart_service.py` (CartService class) | `product_service.py` (ProductService class) + `inventory_service.py` |
| Key builder | `_cart_key()`, `_meta_key()` | `_product_key()`, `_list_key()` |

---

> **Padhne ke baad**: Agar koi interview mein poochta hai "ek project mein 2 alag caching layers banayi, farak samjhao" — is doc ke Section 7 (summary table) seedha bol sakte ho, aur Section 8 ke Q&A se follow-up questions handle kar sakte ho.
