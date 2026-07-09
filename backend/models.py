from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, LargeBinary, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from database import Base


class Organizer(Base):
    __tablename__ = "organizers"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    events = relationship("Event", back_populates="organizer")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    faculty = Column(String, nullable=True)   # e.g. "工学部", "経営学部"
    grade = Column(Integer, nullable=True)    # year: 1, 2, 3, 4
    created_at = Column(DateTime, default=datetime.utcnow)

    applications = relationship("Application", back_populates="student")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    image = Column(LargeBinary)                 # raw image bytes, stored directly in Postgres
    image_content_type = Column(String)          # e.g. "image/jpeg"
    team_size = Column(Integer, nullable=False)
    max_participants = Column(Integer, nullable=True)  # total event capacity; None = unlimited
    deadline = Column(DateTime, nullable=True)   # applications close after this time
    category = Column(String, nullable=False, default="event")
    # category values: "event" (イベント), "club" (部活・サークル),
    # "seminar" (ゼミ), "research" (研究), "career" (就職・インターンシップ)
    organizer_id = Column(Integer, ForeignKey("organizers.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    organizer = relationship("Organizer", back_populates="events")
    applications = relationship("Application", back_populates="event", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="event", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="event", cascade="all, delete-orphan")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)

    # Denormalized copies taken at time of application, so organizer views
    # and team lists don't need extra joins, and stay stable even if a
    # student later edits their profile.
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    grade = Column(String)      # kept as string for backward compatibility (e.g. "1st year")
    faculty = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="applications")
    student = relationship("Student", back_populates="applications")
    team_membership = relationship("TeamMember", back_populates="application", uselist=False)


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)

    author_type = Column(String, nullable=False)  # "student" or "organizer"
    author_id = Column(Integer, nullable=False)    # student.id or organizer.id, depending on author_type
    author_name = Column(String, nullable=False)   # denormalized for easy display

    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="comments")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    team_number = Column(Integer)
    group_label = Column(String, nullable=True)  # e.g. "1年生グループ", "2年生グループ", "混合グループ"

    event = relationship("Event", back_populates="teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    application_id = Column(Integer, ForeignKey("applications.id"))

    team = relationship("Team", back_populates="members")
    application = relationship("Application", back_populates="team_membership")