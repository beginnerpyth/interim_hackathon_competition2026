from datetime import datetime
from typing import List

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload

import auth
import matching
import models
import schemas
from database import Base, SessionLocal, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Campus Event Team Matcher")

# For the hackathon, allow all origins. Tighten this to your actual frontend
# Render URL once you know it (e.g. allow_origins=["https://your-frontend.onrender.com"]).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "message": "Campus Event Team Matcher API"}


# ============================================================
# ORGANIZER AUTH
# ============================================================

@app.post("/organizer/register", response_model=schemas.Token)
def register_organizer(data: schemas.OrganizerCreate, db: Session = Depends(get_db)):
    """
    Creates a new organizer account. In a real product you'd lock this down
    (e.g. invite-only), but for a hackathon it's fine to leave open so any
    club leader can self-register.
    """
    existing = db.query(models.Organizer).filter(models.Organizer.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    organizer = models.Organizer(
        username=data.username,
        hashed_password=auth.hash_password(data.password),
    )
    db.add(organizer)
    db.commit()
    db.refresh(organizer)

    token = auth.create_access_token({"sub": organizer.username})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/organizer/login", response_model=schemas.Token)
def login_organizer(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    organizer = db.query(models.Organizer).filter(models.Organizer.username == form_data.username).first()
    if not organizer or not auth.verify_password(form_data.password, organizer.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = auth.create_access_token({"sub": organizer.username})
    return {"access_token": token, "token_type": "bearer"}


# ============================================================
# EVENTS
# ============================================================

@app.post("/events", response_model=schemas.EventOut)
async def create_event(
    title: str = Form(...),
    description: str = Form(""),
    team_size: int = Form(...),
    deadline: str = Form(None),  # ISO datetime string from a <input type="datetime-local">, e.g. "2026-07-10T15:30"
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    organizer: models.Organizer = Depends(auth.get_current_organizer),
):
    image_bytes = await file.read() if file else None
    content_type = file.content_type if file else None

    deadline_dt = None
    if deadline:
        try:
            deadline_dt = datetime.fromisoformat(deadline)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid deadline format")

    event = models.Event(
        title=title,
        description=description,
        team_size=team_size,
        deadline=deadline_dt,
        image=image_bytes,
        image_content_type=content_type,
        organizer_id=organizer.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@app.get("/events", response_model=List[schemas.EventOut])
def list_events(db: Session = Depends(get_db)):
    return db.query(models.Event).order_by(models.Event.created_at.desc()).all()


@app.get("/events/{event_id}", response_model=schemas.EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.get("/events/{event_id}/image")
def get_event_image(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event or not event.image:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=event.image, media_type=event.image_content_type or "image/jpeg")


@app.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    organizer: models.Organizer = Depends(auth.get_current_organizer),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != organizer.id:
        raise HTTPException(status_code=403, detail="You can only delete your own events")

    # Cascade delete removes related applications, teams, and team_members automatically
    # (set up via cascade="all, delete-orphan" in models.py).
    db.delete(event)
    db.commit()
    return {"message": "Event deleted"}


# ============================================================
# APPLICATIONS (students apply here — just name, email, grade)
# ============================================================

@app.post("/events/{event_id}/apply", response_model=schemas.ApplicationOut)
def apply_to_event(event_id: int, data: schemas.ApplicationCreate, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.deadline and datetime.utcnow() > event.deadline:
        raise HTTPException(status_code=400, detail="Applications are closed for this event")

    # Prevent the same student (by email) from applying twice to the same event —
    # without this, a double form-submit or refresh could put someone on two teams.
    existing = (
        db.query(models.Application)
        .filter(
            models.Application.event_id == event_id,
            models.Application.email == data.email,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="This email has already applied to this event")

    application = models.Application(
        event_id=event_id,
        name=data.name,
        email=data.email,
        grade=data.grade,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@app.get("/events/{event_id}/applications", response_model=List[schemas.ApplicationOut])
def list_applications(
    event_id: int,
    db: Session = Depends(get_db),
    organizer: models.Organizer = Depends(auth.get_current_organizer),
):
    """Organizer-only: see who has applied so far. Only the event's own organizer may view this."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != organizer.id:
        raise HTTPException(status_code=403, detail="You can only view applications for your own events")

    return db.query(models.Application).filter(models.Application.event_id == event_id).all()


# ============================================================
# TEAM GENERATION (random)
# ============================================================

@app.post("/events/{event_id}/generate-teams")
def generate_teams(
    event_id: int,
    db: Session = Depends(get_db),
    organizer: models.Organizer = Depends(auth.get_current_organizer),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != organizer.id:
        raise HTTPException(status_code=403, detail="You can only generate teams for your own events")

    # Clear any previously generated teams so the organizer can re-roll.
    db.query(models.Team).filter(models.Team.event_id == event_id).delete()
    db.commit()

    applications = db.query(models.Application).filter(models.Application.event_id == event_id).all()
    if not applications:
        raise HTTPException(status_code=400, detail="No applications yet for this event")

    grouped = matching.create_random_teams(applications, event.team_size)

    for idx, group in enumerate(grouped, start=1):
        team = models.Team(event_id=event_id, team_number=idx)
        db.add(team)
        db.flush()  # get team.id before commit
        for applicant in group:
            db.add(models.TeamMember(team_id=team.id, application_id=applicant.id))

    db.commit()
    return {"message": f"{len(grouped)} teams created", "team_count": len(grouped)}


@app.get("/events/{event_id}/teams", response_model=List[schemas.TeamOut])
def get_teams(event_id: int, db: Session = Depends(get_db)):
    teams = (
        db.query(models.Team)
        .options(joinedload(models.Team.members).joinedload(models.TeamMember.application))
        .filter(models.Team.event_id == event_id)
        .order_by(models.Team.team_number)
        .all()
    )

    result = []
    for team in teams:
        members = [
            schemas.TeamMemberOut(
                name=m.application.name,
                email=m.application.email,
                grade=m.application.grade,
            )
            for m in team.members
        ]
        result.append(schemas.TeamOut(team_number=team.team_number, members=members))
    return result


# ============================================================
# AUTOMATIC TEAM GENERATION AFTER DEADLINE
# ============================================================

def auto_generate_teams_for_expired_events():
    """
    Runs periodically in the background. For any event whose deadline has
    passed and that doesn't have teams yet, automatically generates them.
    Organizers can still click "Generate Teams" manually beforehand if they
    want to close applications early — this only fires for events that
    reach their deadline with no teams generated yet.
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        expired_events = (
            db.query(models.Event)
            .filter(models.Event.deadline.isnot(None), models.Event.deadline <= now)
            .all()
        )

        for event in expired_events:
            already_has_teams = db.query(models.Team).filter(models.Team.event_id == event.id).first()
            if already_has_teams:
                continue  # teams already generated (manually or by a previous run) — skip

            applications = db.query(models.Application).filter(models.Application.event_id == event.id).all()
            if not applications:
                continue  # nobody applied, nothing to do

            grouped = matching.create_random_teams(applications, event.team_size)
            for idx, group in enumerate(grouped, start=1):
                team = models.Team(event_id=event.id, team_number=idx)
                db.add(team)
                db.flush()
                for applicant in group:
                    db.add(models.TeamMember(team_id=team.id, application_id=applicant.id))

            db.commit()
    finally:
        db.close()


scheduler = BackgroundScheduler()


@app.on_event("startup")
def start_scheduler():
    # Checks every 30 seconds for events that just passed their deadline.
    scheduler.add_job(auto_generate_teams_for_expired_events, "interval", seconds=30)
    scheduler.start()


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()