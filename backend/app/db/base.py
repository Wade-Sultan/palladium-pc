from sqlalchemy.orm import declarative_base

Base = declarative_base()

from app.models.user import User
from app.models.conversation import Conversation
from app.models.pcparts import PCPart
from app.models.pcbuild import PCBuild, BuildPart