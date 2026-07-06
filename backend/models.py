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


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    image = Column(LargeBinary)                 # raw image bytes, stored directly in Postgres
    image_content_type = Column(String)          # e.g. "image/jpeg"
    team_size = Column(Integer, nullable=False)
    deadline = Column(DateTime, nullable=True)   # applications close after this time
    organizer_id = Column(Integer, ForeignKey("organizers.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    organizer = relationship("Organizer", back_populates="events")
    applications = relationship("Application", back_populates="event", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="event", cascade="all, delete-orphan")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    grade = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="applications")
    team_membership = relationship("TeamMember", back_populates="application", uselist=False)


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    team_number = Column(Integer)

    event = relationship("Event", back_populates="teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    application_id = Column(Integer, ForeignKey("applications.id"))

    team = relationship("Team", back_populates="members")
    application = relationship("Application", back_populates="team_membership")
