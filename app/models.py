
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from enum import Enum


## MODELS ##

# user models 
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    hashed_password : str
    is_Active : bool = Field(default=True)
    photos: List["Photo"] = Relationship(back_populates="owner")


# image models
class TransformStatus(str, Enum):
    one = "Original"
    two = "Pending alterations"
    three = "Altered"

class Photo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    s3_uri : str | None
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="photos")
    version: Optional[int] = Field(default=1)



