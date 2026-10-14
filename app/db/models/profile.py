import uuid
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class UserProfile(Base, TimestampMixin):
    """
    Persistent user profile memory.
    Stores structured facts about the student to personalize explanations,
    pedagogical tone, and academic context across all conversations.
    """
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    preferred_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    academic_institution: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    academic_discipline: Mapped[Optional[str]] = mapped_column(String(255), default="General Studies", nullable=True)
    current_level: Mapped[Optional[str]] = mapped_column(String(100), default="Undergraduate", nullable=True)
    explanation_style: Mapped[Optional[str]] = mapped_column(String(100), default="intuitive_first", nullable=True)
    learning_goals: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list, nullable=True)
    preferences_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="profile")
