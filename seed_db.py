import asyncio
import uuid
import random
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from slugify import slugify
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.models.product import Category, Product
from app.db.models.coupon import Coupon, DiscountType
from app.core.config import settings

CATEGORIES = {
    "Electronics": ["Smartphone", "Tablet", "Laptop", "Smartwatch", "Headphones", "Earbuds", "Monitor", "Keyboard", "Mouse", "Speaker"],
    "Men's Clothing": ["T-Shirt", "Jeans", "Jacket", "Sweater", "Hoodie", "Shorts", "Polo Shirt", "Formal Shirt", "Chinos", "Track Pants"],
    "Women's Clothing": ["Dress", "Top", "Jeans", "Skirt", "Sweater", "Jacket", "Activewear", "T-Shirt", "Blouse", "Leggings"],
    "Home & Kitchen": ["Coffee Maker", "Blender", "Toaster", "Microwave", "Air Fryer", "Cookware Set", "Cutlery Set", "Dinnerware", "Vacuum Cleaner", "Iron"],
    "Sports & Outdoors": ["Yoga Mat", "Dumbbells", "Resistance Bands", "Jump Rope", "Water Bottle", "Tent", "Sleeping Bag", "Backpack", "Treadmill", "Exercise Bike"],
    "Books": ["Fiction Novel", "Non-Fiction", "Sci-Fi", "Fantasy", "Mystery", "Biography", "Self-Help", "Cookbook", "History", "Business"],
    "Health & Personal Care": ["Shampoo", "Conditioner", "Body Wash", "Toothpaste", "Toothbrush", "Deodorant", "Moisturizer", "Sunscreen", "Vitamins", "Protein Powder"],
    "Toys & Games": ["Board Game", "Puzzle", "Action Figure", "Doll", "Building Blocks", "Remote Control Car", "Stuffed Animal", "Card Game", "Educational Toy", "Video Game"],
    "Automotive": ["Car Wash Soap", "Wax", "Tire Inflator", "Jump Starter", "Dash Cam", "Phone Mount", "Floor Mats", "Seat Covers", "Air Freshener", "Wiper Blades"],
    "Beauty": ["Lipstick", "Foundation", "Mascara", "Eyeshadow Palette", "Eyeliner", "Blush", "Highlighter", "Makeup Brushes", "Perfume", "Nail Polish"]
}

BRANDS = ["Alpha", "Quantum", "Nexus", "Zenith", "Apex", "Nova", "Vortex", "Horizon", "Pinnacle", "Aura"]
ADJECTIVES = ["Premium", "Pro", "Max", "Ultra", "Lite", "Plus", "Advanced", "Elite", "Essential", "Classic"]

FEATURED_PRODUCTS = {
    "Earbuds": {
        "name": "Zenith Earbuds Premium",
        "description": "Active Noise Cancellation (ANC), 36-hour battery life, IPX5 water resistance, and studio-grade audio drivers.",
        "price": Decimal("2499.00"),
        "attributes": {"brand": "Zenith", "battery": "36 hours", "water_resistance": "IPX5", "audio": "Studio-grade drivers"},
    },
    "Monitor": {
        "name": "Nexus Monitor Ultra",
        "description": "27-inch 4K UHD IPS display, 144Hz refresh rate, 1ms response time, and HDR400 color calibration.",
        "price": Decimal("24799.00"),
        "attributes": {"brand": "Nexus", "display": "27-inch 4K UHD IPS", "refresh_rate": "144Hz", "response_time": "1ms", "color": "HDR400"},
    },
    "Keyboard": {
        "name": "Nexus Keyboard Classic",
        "description": "Hot-swappable tactile mechanical switches, per-key RGB backlighting, aircraft-grade aluminum top frame.",
        "price": Decimal("4899.00"),
        "attributes": {"brand": "Nexus", "switches": "Hot-swappable tactile mechanical", "lighting": "Per-key RGB", "frame": "Aircraft-grade aluminum"},
    },
    "Mouse": {
        "name": "Quantum Mouse Plus",
        "description": "Ergonomic 58g ultra-lightweight design, 26,000 DPI optical sensor, and low-latency wireless.",
        "price": Decimal("2999.00"),
        "attributes": {"brand": "Quantum", "weight": "58g", "sensor": "26,000 DPI optical", "connectivity": "Low-latency wireless"},
    },
}

async def seed():
    print("Starting database seed...")
    engine = create_async_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with SessionLocal() as db:
        for cat_name, items in CATEGORIES.items():
            print(f"Creating category: {cat_name}")
            cat = Category(name=cat_name, slug=slugify(cat_name + "-" + str(uuid.uuid4())[:4]))
            db.add(cat)
            await db.flush()
            
            for item in items:
                featured = FEATURED_PRODUCTS.get(item) if cat_name == "Electronics" else None
                brand = featured["attributes"]["brand"] if featured else random.choice(BRANDS)
                adj = "Featured" if featured else random.choice(ADJECTIVES)
                prod_name = featured["name"] if featured else f"{brand} {item} {adj}"
                price = featured["price"] if featured else Decimal(random.randint(500, 25000))
                
                prod = Product(
                    name=prod_name,
                    slug=slugify(prod_name + "-" + str(uuid.uuid4())[:6]),
                    description=featured["description"] if featured else f"Experience the best with {brand}'s new {item}. Features {adj.lower()} technology for ultimate performance and reliability. Perfect for everyday use.",
                    price=price,
                    stock_quantity=random.randint(10, 500),
                    category_id=cat.id,
                    attributes=featured["attributes"] if featured else {"brand": brand, "model": f"{adj} 2026", "rating": random.choice(["4.5", "4.8", "4.2", "5.0"])}
                )
                db.add(prod)
                
        print("Creating coupons...")
        coupons = [
            Coupon(
                code="WELCOME50", discount_type=DiscountType.FLAT, discount_value=Decimal("50.00"),
                min_order_value=Decimal("0.00"), max_total_uses=1000, max_uses_per_user=1,
                valid_from=datetime.now(timezone.utc), valid_until=datetime.now(timezone.utc) + timedelta(days=365)
            ),
            Coupon(
                code="FESTIVE20", discount_type=DiscountType.PERCENTAGE, discount_value=Decimal("20.00"),
                min_order_value=Decimal("500.00"), max_discount_cap=Decimal("1000.00"), max_total_uses=500, max_uses_per_user=2,
                valid_from=datetime.now(timezone.utc), valid_until=datetime.now(timezone.utc) + timedelta(days=365)
            ),
            Coupon(
                code="FREESHIP", discount_type=DiscountType.FLAT, discount_value=Decimal("100.00"),
                min_order_value=Decimal("1000.00"), max_total_uses=10000, max_uses_per_user=5,
                valid_from=datetime.now(timezone.utc), valid_until=datetime.now(timezone.utc) + timedelta(days=365)
            )
        ]
        db.add_all(coupons)
        
        await db.commit()
        print("Database seeded successfully with 10 categories, 100 products, and 3 coupons!")

if __name__ == "__main__":
    asyncio.run(seed())
