from sqlalchemy import Column, String, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from app.db.base_class import Base

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String, nullable=False, index=True) # Indexed for fast querying
    payload = Column(JSONB, nullable=False) # MUST be JSONB for Postgres (security & speed)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())