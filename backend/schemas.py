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


# ---------- Events ----------

class EventOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    team_size: int
    deadline: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Applications ----------

class ApplicationCreate(BaseModel):
    name: str
    email: EmailStr
    grade: Optional[str] = None


class ApplicationOut(BaseModel):
    id: int
    name: str
    email: str
    grade: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------- Teams ----------

class TeamMemberOut(BaseModel):
    name: str
    email: str
    grade: Optional[str] = None


class TeamOut(BaseModel):
    team_number: int
    members: List[TeamMemberOut]
