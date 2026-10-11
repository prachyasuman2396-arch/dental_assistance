import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class StudyCard(Base, TimestampMixin):
    __tablename__ = "study_cards"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    card_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # flashcard, mcq, viva
    topic: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    options: Mapped[Optional[dict]] = mapped_column(JSON, default=list, nullable=True)  # for MCQs
    difficulty: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="study_cards")
