import uuid
from datetime import datetime

from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chat, Message, PricelistItem, PricelistUpload


async def get_chats(db: AsyncSession) -> list[Chat]:
    result = await db.execute(select(Chat).order_by(Chat.updated_at.desc()))
    return result.scalars().all()


async def create_chat(db: AsyncSession) -> Chat:
    chat = Chat()
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


async def delete_chat(db: AsyncSession, chat_id: uuid.UUID) -> None:
    await db.execute(delete(Chat).where(Chat.id == chat_id))
    await db.commit()


async def get_messages(db: AsyncSession, chat_id: uuid.UUID) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at)
    )
    return result.scalars().all()


async def save_message(
    db: AsyncSession,
    chat_id: uuid.UUID,
    role: str,
    content: str,
) -> Message:
    msg = Message(chat_id=chat_id, role=role, content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def update_chat_title(
    db: AsyncSession,
    chat_id: uuid.UUID,
    title: str,
) -> None:
    await db.execute(update(Chat).where(Chat.id == chat_id).values(title=title))
    await db.commit()


async def bulk_insert_pricelist_items(
    db: AsyncSession, items: list[dict], *, upload_id: uuid.UUID | None = None
) -> int:
    await db.execute(
        insert(PricelistItem),
        [
            {
                "id": uuid.uuid4(),
                "pn": row["pn"],
                "mnf": row.get("mnf", ""),
                "description": row.get("description", ""),
                "moq_1": row.get("moq_1"),
                "price_1": row.get("price_1"),
                "moq_2": row.get("moq_2"),
                "price_2": row.get("price_2"),
                "moq_3": row.get("moq_3"),
                "price_3": row.get("price_3"),
                "moq_4": row.get("moq_4"),
                "price_4": row.get("price_4"),
                "leadtime": row.get("leadtime", ""),
                "price_start": row.get("price_start"),
                "price_end": row.get("price_end"),
                "upload_id": upload_id,
                "ingested_at": datetime.utcnow(),
            }
            for row in items
        ],
    )
    await db.commit()
    return len(items)


async def create_pricelist_upload(
    db: AsyncSession, filename: str, row_count: int, *, upload_id: uuid.UUID | None = None
) -> PricelistUpload:
    record = PricelistUpload(id=upload_id or uuid.uuid4(), filename=filename, row_count=row_count)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def delete_pricelist_upload(db: AsyncSession, upload_id: uuid.UUID) -> bool:
    result = await db.execute(select(PricelistUpload).where(PricelistUpload.id == upload_id))
    record = result.scalar_one_or_none()
    if not record:
        return False
    await db.execute(delete(PricelistItem).where(PricelistItem.upload_id == upload_id))
    await db.delete(record)
    await db.commit()
    return True


async def get_pricelist_uploads(db: AsyncSession) -> list[PricelistUpload]:
    result = await db.execute(select(PricelistUpload).order_by(PricelistUpload.ingested_at.desc()))
    return result.scalars().all()


async def search_pricelist_by_pn(
    db: AsyncSession, pn: str, active_only: bool = True
) -> list[PricelistItem]:
    query = select(PricelistItem).where(PricelistItem.pn == pn)
    if active_only:
        today = datetime.utcnow().date()
        query = query.where(
            or_(
                PricelistItem.price_start.is_(None),
                PricelistItem.price_start <= today,
            ),
            or_(
                PricelistItem.price_end.is_(None),
                PricelistItem.price_end >= today,
            ),
        )
    query = query.order_by(PricelistItem.ingested_at.desc())
    result = await db.execute(query)
    return result.scalars().all()
