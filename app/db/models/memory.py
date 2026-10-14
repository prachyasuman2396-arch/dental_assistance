import uuid
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Integer, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class LongTermMemory(Base, TimestampMixin):
    """
    Persistent long-term learning memory.
    Stores cross-conversation facts such as saved topics, study goals,
    revision progress, summaries, and topics requiring further study.
    """
    __tablename__ = "long_term_memories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    memory_type: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # "preference", "saved_topic", "study_goal", "revision_topic", "summary", "study_plan"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    importance: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="memories")

    __table_args__ = (
        Index("ix_lt_memories_user_type", "user_id", "memory_type"),
    )
