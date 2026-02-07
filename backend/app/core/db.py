from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app import crud
from app.core.config import settings
from app.models import User
from app.schemas import UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db(session: Session) -> None:
    user = session.execute(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).scalar_one_or_none()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        crud.create_user(session=session, user_create=user_in)
