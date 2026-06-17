import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.db import Base


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(Uuid(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    chat = relationship("Chat", back_populates="messages")


Index("ix_messages_chat_id", Message.chat_id)


class PricelistItem(Base):
    __tablename__ = "pricelist_items"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pn = Column(String(100), nullable=False)
    mnf = Column(String(200), default="")
    description = Column(Text, default="")
    moq_1 = Column(Integer, nullable=True)
    price_1 = Column(Float, nullable=True)
    moq_2 = Column(Integer, nullable=True)
    price_2 = Column(Float, nullable=True)
    moq_3 = Column(Integer, nullable=True)
    price_3 = Column(Float, nullable=True)
    moq_4 = Column(Integer, nullable=True)
    price_4 = Column(Float, nullable=True)
    leadtime = Column(String(100), default="")
    price_start = Column(Date, nullable=True)
    price_end = Column(Date, nullable=True)
    upload_id = Column(Uuid(as_uuid=True), nullable=True, index=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)


Index("ix_pricelist_pn_dates", PricelistItem.pn, PricelistItem.price_start, PricelistItem.price_end)


class PricelistUpload(Base):
    __tablename__ = "pricelist_uploads"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    row_count = Column(Integer, nullable=False)
    ingested_at = Column(DateTime, default=datetime.utcnow)
