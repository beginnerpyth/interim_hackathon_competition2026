from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr


# ---------- Organizer / Auth ----------

class OrganizerCreate(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


# ---------- Students ----------

class StudentCreate(BaseModel):
    username: str
    password: str
    name: str
    email: EmailStr
    faculty: Optional[str] = None
    grade: Optional[int] = None


class StudentOut(BaseModel):
    id: int
    username: str
    name: str
    email: str
    faculty: Optional[str] = None
    grade: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ---------- Events ----------

class EventOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    team_size: int
    max_participants: Optional[int] = None
    current_participants: int = 0
    deadline: Optional[datetime] = None
    category: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Applications ----------

class TeamApplyRequest(BaseModel):
    """
    Used when a student applies as a pre-formed team rather than
    individually. `teammate_usernames` must list every OTHER member's
    username (not the leader's own) — the backend validates the count
    matches the event's team_size exactly.
    """
    teammate_usernames: List[str]


class ApplicationOut(BaseModel):
    id: int
    name: str
    email: str
    grade: Optional[str] = None
    faculty: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------- AI 相談 (consultation chat) ----------

class AiConsultRequest(BaseModel):
    message: str


class AiConsultResponse(BaseModel):
    reply: str


# ---------- Comments (Q&A on each event/club posting) ----------

class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    author_type: str   # "student" or "organizer"
    author_name: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Teams ----------

class TeamMemberOut(BaseModel):
    application_id: int
    name: str
    email: str
    grade: Optional[str] = None
    faculty: Optional[str] = None


class TeamOut(BaseModel):
    id: int
    team_number: int
    group_label: Optional[str] = None
    members: List[TeamMemberOut]