from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import UserCreate


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, data: UserCreate) -> User:
        existing = (
            self.db.query(User).filter(User.email == data.email.lower().strip()).first()
        )
        if existing:
            raise ValueError("Email already registered")

        user = User(
            email=data.email.lower().strip(),
            full_name=data.full_name,
            password_hash=hash_password(data.password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> User | None:
        user = self.db.query(User).filter(User.email == email.lower().strip()).first()
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user
