import os
from datetime import datetime, timedelta

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

import models
from database import get_db

load_dotenv()

# IMPORTANT: set a real SECRET_KEY as an environment variable on Render.
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-before-deploying")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 720  # 12 hours — plenty for a hackathon day

# Two separate token URLs so Swagger's "Authorize" button knows which login
# flow it's testing, but both produce/verify JWTs the same way.
organizer_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/organizer/login", auto_error=False)
student_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/student/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict) -> str:
    """
    `data` must include a "role" key ("organizer" or "student") in addition
    to "sub" (the username), so a student's token can never be used to call
    organizer-only endpoints and vice versa.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise credentials_exception
    return payload


def get_current_organizer(
    token: str = Depends(organizer_oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.Organizer:
    payload = _decode_token(token)
    if payload.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Organizer account required")

    username = payload.get("sub")
    organizer = db.query(models.Organizer).filter(models.Organizer.username == username).first()
    if organizer is None:
        raise HTTPException(status_code=401, detail="Could not validate organizer credentials")
    return organizer


def get_current_user_any(
    token: str = Depends(organizer_oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    For endpoints (like comments) that any logged-in account — student OR
    organizer — should be able to use. Returns a dict with "role" and
    "user" so the caller can branch on which kind of account it is.
    """
    payload = _decode_token(token)
    role = payload.get("role")
    username = payload.get("sub")

    if role == "student":
        user = db.query(models.Student).filter(models.Student.username == username).first()
    elif role == "organizer":
        user = db.query(models.Organizer).filter(models.Organizer.username == username).first()
    else:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    if user is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    return {"role": role, "user": user}


def get_current_student(
    token: str = Depends(student_oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.Student:
    payload = _decode_token(token)
    if payload.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student account required")

    username = payload.get("sub")
    student = db.query(models.Student).filter(models.Student.username == username).first()
    if student is None:
        raise HTTPException(status_code=401, detail="Could not validate student credentials")
    return student