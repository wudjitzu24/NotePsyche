import os
import json
from typing import Optional, Dict
from datetime import datetime, timedelta

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# JWT / password config
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_PATH = os.path.join(BASE_DIR, "users.json")


def _ensure_users_file():
    if not os.path.exists(USERS_PATH):
        with open(USERS_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)


def get_user(username: str) -> Optional[Dict]:
    _ensure_users_file()
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            users = json.load(f)
    except Exception:
        users = {}
    return users.get(username.lower())


def save_user(username: str, hashed_password: str) -> None:
    _ensure_users_file()
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            users = json.load(f)
    except Exception:
        users = {}
    users[username.lower()] = {"hashed_password": hashed_password}
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.get("hashed_password", "")):
        return None
    return {"username": username}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = dict(data)
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    username = payload.get("sub") or payload.get("username")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return {"username": username}


def register_user(username: str, password: str) -> bool:
    username = username.lower()
    if get_user(username):
        return False
    hashed = get_password_hash(password)
    save_user(username, hashed)
    return True


__all__ = [
    "authenticate_user",
    "create_access_token",
    "get_current_user",
    "register_user",
]
