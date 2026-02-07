import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models import Item, User
from app.schemas import ItemCreate, UserCreate, UserUpdate


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User(
        email=user_create.email,
        full_name=user_create.full_name,
        is_active=user_create.is_active,
        is_superuser=user_create.is_superuser,
        hashed_password=get_password_hash(user_create.password),
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.model_dump(exclude_unset=True)

    if "email" in user_data:
        db_user.email = user_data["email"]
    if "is_active" in user_data:
        db_user.is_active = user_data["is_active"]
    if "is_superuser" in user_data:
        db_user.is_superuser = user_data["is_superuser"]
    if "full_name" in user_data:
        db_user.full_name = user_data["full_name"]

    if user_data.get("password"):
        db_user.hashed_password = get_password_hash(user_data["password"])

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return session.execute(statement).scalar_one_or_none()


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item(
        title=item_in.title,
        description=item_in.description,
        owner_id=owner_id,
    )
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item
