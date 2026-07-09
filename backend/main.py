from datetime import datetime
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload

import ai
import auth
import matching
import models
import schemas
from database import Base, SessionLocal, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Campus Event Team Matcher")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_CATEGORIES = {"event", "club", "seminar", "research", "career"}


@app.get("/")
def root():
    return {"status": "ok", "message": "Campus Event Team Matcher API"}


# ============================================================
# ORGANIZER AUTH
# ============================================================

@app.post("/organizer/register", response_model=schemas.Token)
def register_organizer(data: schemas.OrganizerCreate, db: Session = Depends(get_db)):
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

    token = auth.create_access_token({"sub": organizer.username, "role": "organizer"})
    return {"access_token": token, "token_type": "bearer", "role": "organizer"}


@app.post("/organizer/login", response_model=schemas.Token)
def login_organizer(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    organizer = db.query(models.Organizer).filter(models.Organizer.username == form_data.username).first()
    if not organizer or not auth.verify_password(form_data.password, organizer.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = auth.create_access_token({"sub": organizer.username, "role": "organizer"})
    return {"access_token": token, "token_type": "bearer", "role": "organizer"}


# ============================================================
# STUDENT AUTH
# ============================================================

@app.post("/student/register", response_model=schemas.Token)
def register_student(data: schemas.StudentCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Student).filter(models.Student.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    student = models.Student(
        username=data.username,
        hashed_password=auth.hash_password(data.password),
        name=data.name,
        email=data.email,
        faculty=data.faculty,
        grade=data.grade,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    token = auth.create_access_token({"sub": student.username, "role": "student"})
    return {"access_token": token, "token_type": "bearer", "role": "student"}


@app.post("/student/login", response_model=schemas.Token)
def login_student(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.username == form_data.username).first()
    if not student or not auth.verify_password(form_data.password, student.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = auth.create_access_token({"sub": student.username, "role": "student"})
    return {"access_token": token, "token_type": "bearer", "role": "student"}


@app.get("/student/me", response_model=schemas.StudentOut)
def get_my_profile(student: models.Student = Depends(auth.get_current_student)):
    return student


# ============================================================
# EVENTS
# ============================================================

def _event_to_out(db: Session, event: models.Event) -> schemas.EventOut:
    current_count = db.query(models.Application).filter(models.Application.event_id == event.id).count()
    return schemas.EventOut(
        id=event.id,
        title=event.title,
        description=event.description,
        team_size=event.team_size,
        max_participants=event.max_participants,
        current_participants=current_count,
        deadline=event.deadline,
        category=event.category,
        created_at=event.created_at,
    )


@app.post("/events", response_model=schemas.EventOut)
async def create_event(
    title: str = Form(...),
    description: str = Form(""),
    team_size: int = Form(...),
    max_participants: Optional[int] = Form(None),
    deadline: str = Form(None),
    category: str = Form("event"),
    db: Session = Depends(get_db),
    file: UploadFile = File(None),
    organizer: models.Organizer = Depends(auth.get_current_organizer),
):
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {sorted(VALID_CATEGORIES)}")

    if max_participants is not None and max_participants < team_size:
        raise HTTPException(status_code=400, detail="定員はチーム人数以上に設定してください。")

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
        max_participants=max_participants,
        deadline=deadline_dt,
        category=category,
        image=image_bytes,
        image_content_type=content_type,
        organizer_id=organizer.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _event_to_out(db, event)


@app.get("/events", response_model=List[schemas.EventOut])
def list_events(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Event)
    if category:
        query = query.filter(models.Event.category == category)
    events = query.order_by(models.Event.created_at.desc()).all()
    return [_event_to_out(db, e) for e in events]


@app.get("/events/{event_id}", response_model=schemas.EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_out(db, event)


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

    db.delete(event)
    db.commit()
    return {"message": "Event deleted"}


# ============================================================
# APPLICATIONS
# ============================================================

@app.post("/events/{event_id}/apply", response_model=schemas.ApplicationOut)
def apply_to_event(
    event_id: int,
    db: Session = Depends(get_db),
    student: models.Student = Depends(auth.get_current_student),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.deadline and datetime.utcnow() > event.deadline:
        raise HTTPException(status_code=400, detail="Applications are closed for this event")

    if event.max_participants is not None:
        current_count = db.query(models.Application).filter(models.Application.event_id == event_id).count()
        if current_count >= event.max_participants:
            raise HTTPException(status_code=400, detail="定員に達しているため、応募できません。")

    existing = (
        db.query(models.Application)
        .filter(
            models.Application.event_id == event_id,
            models.Application.student_id == student.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="You have already applied to this event")

    application = models.Application(
        event_id=event_id,
        student_id=student.id,
        name=student.name,
        email=student.email,
        grade=str(student.grade) if student.grade else None,
        faculty=student.faculty,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@app.post("/events/{event_id}/apply-team", response_model=schemas.TeamOut)
def apply_as_team(
    event_id: int,
    data: schemas.TeamApplyRequest,
    db: Session = Depends(get_db),
    leader: models.Student = Depends(auth.get_current_student),
):
    """
    Leader applies on behalf of a pre-formed team. `teammate_usernames`
    must contain every OTHER member (not the leader) and the total size
    (leader + teammates) must exactly equal the event's team_size —
    no more, no fewer.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.deadline and datetime.utcnow() > event.deadline:
        raise HTTPException(status_code=400, detail="Applications are closed for this event")

    if event.max_participants is not None:
        current_count = db.query(models.Application).filter(models.Application.event_id == event_id).count()
        if current_count + event.team_size > event.max_participants:
            remaining = max(0, event.max_participants - current_count)
            raise HTTPException(
                status_code=400,
                detail=f"定員に空きがありません（残り{remaining}人）。チーム全員分の枠がありません。",
            )

    usernames = [u.strip() for u in data.teammate_usernames if u.strip()]

    # Exact size check: leader + teammates must equal team_size precisely.
    expected_teammate_count = event.team_size - 1
    if len(usernames) != expected_teammate_count:
        raise HTTPException(
            status_code=400,
            detail=f"このイベントのチーム人数は{event.team_size}人です。あなた以外に{expected_teammate_count}人のユーザー名を入力してください。",
        )

    if leader.username in usernames:
        raise HTTPException(status_code=400, detail="自分自身をチームメイトとして追加することはできません。")

    if len(set(usernames)) != len(usernames):
        raise HTTPException(status_code=400, detail="同じユーザー名が重複しています。")

    # Resolve every teammate username to a real student account.
    teammates = db.query(models.Student).filter(models.Student.username.in_(usernames)).all()
    found_usernames = {s.username for s in teammates}
    missing = set(usernames) - found_usernames
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"次のユーザー名の学生アカウントが見つかりませんでした: {', '.join(missing)}",
        )

    all_members = [leader] + teammates

    # Make sure none of them (including the leader) has already applied.
    member_ids = [m.id for m in all_members]
    existing = (
        db.query(models.Application)
        .filter(
            models.Application.event_id == event_id,
            models.Application.student_id.in_(member_ids),
        )
        .all()
    )
    if existing:
        already_applied_names = {a.name for a in existing}
        raise HTTPException(
            status_code=400,
            detail=f"次のメンバーはすでにこのイベントに応募しています: {', '.join(already_applied_names)}",
        )

    # Create one Application per member, then immediately form their team
    # — pre-formed teams skip the random/year-based matching entirely.
    applications = []
    for member in all_members:
        application = models.Application(
            event_id=event_id,
            student_id=member.id,
            name=member.name,
            email=member.email,
            grade=str(member.grade) if member.grade else None,
            faculty=member.faculty,
        )
        db.add(application)
        applications.append(application)
    db.flush()  # assign IDs to the new applications

    existing_team_count = db.query(models.Team).filter(models.Team.event_id == event_id).count()
    team = models.Team(
        event_id=event_id,
        team_number=existing_team_count + 1,
        group_label="自己編成チーム（友達と応募）",
    )
    db.add(team)
    db.flush()

    for application in applications:
        db.add(models.TeamMember(team_id=team.id, application_id=application.id))

    db.commit()
    db.refresh(team)

    members_out = [
        schemas.TeamMemberOut(
            application_id=app.id,
            name=app.name,
            email=app.email,
            grade=app.grade,
            faculty=app.faculty,
        )
        for app in applications
    ]
    return schemas.TeamOut(id=team.id, team_number=team.team_number, group_label=team.group_label, members=members_out)


@app.get("/events/{event_id}/applications", response_model=List[schemas.ApplicationOut])
def list_applications(
    event_id: int,
    db: Session = Depends(get_db),
    organizer: models.Organizer = Depends(auth.get_current_organizer),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != organizer.id:
        raise HTTPException(status_code=403, detail="You can only view applications for your own events")

    return db.query(models.Application).filter(models.Application.event_id == event_id).all()


@app.get("/student/my-applications", response_model=List[schemas.ApplicationOut])
def my_applications(
    db: Session = Depends(get_db),
    student: models.Student = Depends(auth.get_current_student),
):
    return db.query(models.Application).filter(models.Application.student_id == student.id).all()


# ============================================================
# TEAM GENERATION — grouped by year, with a shared "mixed" group
# for any year that doesn't have enough students for a full team
# ============================================================

def _build_teams_for_event(db: Session, event: models.Event):
    """
    Shared by manual generate-teams and the deadline auto-generator.
    Only matches applications that AREN'T already on a team — students who
    applied via apply-team already have their team locked in and are
    excluded here automatically (team_membership is not None for them).
    """
    applications = (
        db.query(models.Application)
        .filter(
            models.Application.event_id == event.id,
            ~models.Application.id.in_(
                db.query(models.TeamMember.application_id)
            ),
        )
        .all()
    )
    if not applications:
        return 0

    grouped = matching.create_year_grouped_teams(applications, event.team_size)

    existing_team_count = db.query(models.Team).filter(models.Team.event_id == event.id).count()

    for offset, (members, label) in enumerate(grouped, start=1):
        team = models.Team(event_id=event.id, team_number=existing_team_count + offset, group_label=label)
        db.add(team)
        db.flush()
        for applicant in members:
            db.add(models.TeamMember(team_id=team.id, application_id=applicant.id))

    db.commit()
    return len(grouped)


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

    # Only clear previously auto/random-generated teams — pre-formed teams
    # (students who applied together via apply-team) are left untouched.
    db.query(models.Team).filter(
        models.Team.event_id == event_id,
        models.Team.group_label != "自己編成チーム（友達と応募）",
    ).delete()
    db.commit()

    team_count = _build_teams_for_event(db, event)
    if team_count == 0:
        raise HTTPException(status_code=400, detail="No applications yet for this event")

    return {"message": f"{team_count} teams created (grouped by year)", "team_count": team_count}


@app.put("/teams/{team_id}/move-member/{application_id}")
def move_member_to_team(
    team_id: int,
    application_id: int,
    db: Session = Depends(get_db),
    organizer: models.Organizer = Depends(auth.get_current_organizer),
):
    """Lets an organizer manually move a student to a different team after generation."""
    target_team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not target_team:
        raise HTTPException(status_code=404, detail="Target team not found")

    event = db.query(models.Event).filter(models.Event.id == target_team.event_id).first()
    if not event or event.organizer_id != organizer.id:
        raise HTTPException(status_code=403, detail="You can only edit teams for your own events")

    member = (
        db.query(models.TeamMember)
        .filter(models.TeamMember.application_id == application_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="This applicant isn't currently on any team")

    member.team_id = team_id
    db.commit()
    return {"message": "Member moved successfully"}



# ============================================================
# AI 相談 (consultation chat) — powered by Gemini
# ============================================================

# ============================================================
# AI 相談 (Gemini)
# ============================================================

@app.post("/ai/consult", response_model=schemas.AiConsultResponse)
def ai_consult_general(
    data: schemas.AiConsultRequest,
    auth_info: dict = Depends(auth.get_current_user_any),
):
    if not data.message.strip():
        raise HTTPException(
            status_code=400,
            detail="メッセージを入力してください。"
        )

    try:
        reply = ai.ask_gemini(data.message.strip())

        return schemas.AiConsultResponse(
            reply=reply
        )

    except RuntimeError as e:
        print("CONFIG ERROR:", e)
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )

    except Exception as e:
        print("==============================")
        print("GEMINI ERROR:")
        print(type(e))
        print(e)
        print("==============================")

        raise HTTPException(
            status_code=502,
            detail=f"Gemini error: {str(e)}"
        )


@app.post("/events/{event_id}/ai-consult", response_model=schemas.AiConsultResponse)
def ai_consult_event(
    event_id: int,
    data: schemas.AiConsultRequest,
    db: Session = Depends(get_db),
    auth_info: dict = Depends(auth.get_current_user_any),
):
    event = (
        db.query(models.Event)
        .filter(models.Event.id == event_id)
        .first()
    )

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if not data.message.strip():
        raise HTTPException(
            status_code=400,
            detail="メッセージを入力してください。"
        )

    try:
        reply = ai.ask_gemini(
            data.message.strip(),
            event=event
        )

        return schemas.AiConsultResponse(
            reply=reply
        )

    except RuntimeError as e:
        print("CONFIG ERROR:", e)

        raise HTTPException(
            status_code=503,
            detail=str(e)
        )

    except Exception as e:
        print("==============================")
        print("GEMINI ERROR:")
        print(type(e))
        print(e)
        print("==============================")

        raise HTTPException(
            status_code=502,
            detail=f"Gemini error: {str(e)}"
        )


# ============================================================
# COMMENTS — Q&A / discussion thread on each event/club posting
# ============================================================

@app.post("/events/{event_id}/comments", response_model=schemas.CommentOut)
def post_comment(
    event_id: int,
    data: schemas.CommentCreate,
    db: Session = Depends(get_db),
    auth_info: dict = Depends(auth.get_current_user_any),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not data.content.strip():
        raise HTTPException(status_code=400, detail="コメントを入力してください。")

    role = auth_info["role"]
    user = auth_info["user"]
    author_name = user.name if role == "student" else f"{user.username}（主催者）"

    comment = models.Comment(
        event_id=event_id,
        author_type=role,
        author_id=user.id,
        author_name=author_name,
        content=data.content.strip(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@app.get("/events/{event_id}/comments", response_model=List[schemas.CommentOut])
def list_comments(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return (
        db.query(models.Comment)
        .filter(models.Comment.event_id == event_id)
        .order_by(models.Comment.created_at.asc())
        .all()
    )


@app.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    auth_info: dict = Depends(auth.get_current_user_any),
):
    """A comment can be deleted by its own author, or by the event's organizer (moderation)."""
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    role = auth_info["role"]
    user = auth_info["user"]

    is_own_comment = comment.author_type == role and comment.author_id == user.id
    is_event_organizer = False
    if role == "organizer":
        event = db.query(models.Event).filter(models.Event.id == comment.event_id).first()
        is_event_organizer = event is not None and event.organizer_id == user.id

    if not (is_own_comment or is_event_organizer):
        raise HTTPException(status_code=403, detail="このコメントを削除する権限がありません。")

    db.delete(comment)
    db.commit()
    return {"message": "Comment deleted"}


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
                application_id=m.application_id,
                name=m.application.name,
                email=m.application.email,
                grade=m.application.grade,
                faculty=m.application.faculty,
            )
            for m in team.members
        ]
        result.append(schemas.TeamOut(id=team.id, team_number=team.team_number, group_label=team.group_label, members=members))
    return result


# ============================================================
# AUTOMATIC TEAM GENERATION AFTER DEADLINE
# ============================================================

def auto_generate_teams_for_expired_events():
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
                continue
            _build_teams_for_event(db, event)
    finally:
        db.close()


scheduler = BackgroundScheduler()


@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(auto_generate_teams_for_expired_events, "interval", seconds=30)
    scheduler.start()


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()