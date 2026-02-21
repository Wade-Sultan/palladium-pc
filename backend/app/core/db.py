from collections.abc import Generator

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

from app import crud
from app.core.config import settings
from app.models import User
from app.schemas import UserCreate


def _build_engine_kwargs() -> dict:
    kwargs: dict = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }

    if settings.SUPABASE_DB_URL:
        # Supabase-specific tuning
        connect_args: dict = {
            # Supabase requires SSL for remote connections
            "sslmode": "require",
        }

        if settings.DB_USE_CONNECTION_POOLER:
            # Supavisor / pgBouncer in transaction mode:
            # prepared statements are not supported.
            connect_args["prepare_threshold"] = 0

        kwargs["connect_args"] = connect_args

    return kwargs


engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    **_build_engine_kwargs(),
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()


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
