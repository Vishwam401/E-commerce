import uuid
from sqlalchemy import Column, Integer,Numeric, String, Boolean, ForeignKey, Float, Text, DateTime
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from app.db.base import Base
import re



class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda :str(uuid.uuid4()))
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    #soft delete flag
    is_deleted = Column(Boolean, default=False)

    #created_at ko hamne db level pai handle kiya
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @validates('email')
    def validate_email(self, key, address):
        # 1. Lowercase normalization
        address = address.lower()

        #2. Regex validation (Basic)
        if not re.match(r"[^@]+@[^@]+\.[^@]+", address):
            raise ValueError("Invalid email address format")
        return address

    @validates('username')
    def validate_username(self, key, name):
        if len(name) < 3:
            raise ValueError("Username must be at least 3 characters long")
        return name.lower()



#Relationship === 1 to Many
class Category(Base):
    __tablename__ = "categories"

    id = Column(String(36), primary_key=True, default=lambda :str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, index=True,nullable=False)
    description = Column(Text, nullable=True)

    # Relationship: 'products' plural kyuki ek category mai bahot sare products ho sakte hai)
    products = relationship("Product", back_populates="category", cascade="all, delete")


class Product(Base):
    __tablename__ = "products"
    id= Column(String(36), primary_key=True, default=lambda :str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, index=True,nullable=False)
    description = Column(Text)

    #apan numeric use krege price ke liye
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, default=0)
    image_url = Column(String, nullable=True)

    # Foreign key ko category ki ID store karegi
    category_id = Column(String(36), ForeignKey("categories.id"))

    # Relationship jo product object se Category access krne degi
    category = relationship("Category", back_populates="products")
