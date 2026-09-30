from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def seed_admin():
    settings = get_settings()
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if existing:
            print(f"Admin user {settings.ADMIN_EMAIL} already exists.")
            return
        admin = User(
            email=settings.ADMIN_EMAIL,
            full_name="Admin",
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        print(f"Admin user created: {settings.ADMIN_EMAIL}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
