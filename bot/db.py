from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from bot.config import settings

engine = create_async_engine(settings.database_url)
Session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64))
    business_type: Mapped[str | None] = mapped_column(String(64))
    business: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str | None] = mapped_column(Text)
    channels: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str | None] = mapped_column(String(64))
    requests_left: Mapped[int] = mapped_column(Integer, default=settings.free_requests)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @property
    def onboarded(self) -> bool:
        return bool(self.business)

    def profile_text(self) -> str:
        return (
            f"Тип бизнеса: {self.business_type}\n"
            f"Бизнес: {self.business}\n"
            f"Клиенты: {self.audience}\n"
            f"Площадки: {self.channels}\n"
            f"Тон бренда: {self.tone}"
        )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(session: AsyncSession, user_id: int, username: str | None) -> User:
    user = await session.get(User, user_id)
    if user is None:
        user = User(id=user_id, username=username, requests_left=settings.free_requests)
        session.add(user)
        await session.commit()
    return user


async def count_users(session: AsyncSession) -> int:
    return len((await session.execute(select(User.id))).all())
