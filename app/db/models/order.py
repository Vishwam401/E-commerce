import uuid
from sqlalchemy import Column, String
from app.db.base import Base

class Order(Base):
    __tablename__ = "orders"
    id = Column(String(36), primary_key=True, default=lambda :str(uuid.uuid4()))
    # further fields will be added later

