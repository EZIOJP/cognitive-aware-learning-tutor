from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.session import get_db
from backend.models import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)
settings = get_settings()


def token_for(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algo)


def decode_user(token: str, db: Session) -> User | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algo])
        uid = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        return None
    return db.get(User, uid)


def ensure_demo_user(db: Session) -> User:
    demo = db.query(User).filter(User.username == "demo").first()
    if demo:
        if not demo.password_plain:
            demo.password_plain = "demo"
            db.commit()
        return demo
    demo = User(username="demo", password_hash=pwd_context.hash("demo"), password_plain="demo")
    db.add(demo)
    db.commit()
    db.refresh(demo)
    return demo


def ensure_default_admin(db: Session) -> None:
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        changed = False
        if not admin.is_admin:
            admin.is_admin = True
            changed = True
        if not admin.password_plain:
            admin.password_plain = "admin123"
            changed = True
        if changed:
            db.commit()
        return
    admin = User(
        username="admin",
        password_hash=pwd_context.hash("admin123"),
        password_plain="admin123",
        is_admin=True,
    )
    db.add(admin)
    db.commit()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials and credentials.scheme.lower() == "bearer":
        user = decode_user(credentials.credentials, db)
        if user:
            return user
    return ensure_demo_user(db)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)
