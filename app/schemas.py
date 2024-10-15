from pydantic import BaseModel

# user input
class UserInput(BaseModel):
    email: str 
    plain_password: str

# user for public
class UserPublic(BaseModel):
    id: int
    email: str
    is_Active: bool | None = None

# user for internall (full)
class UserPrivate(UserPublic):
    hashed_password: str

    class Config:
        from_attributes = True  # Enables from_orm() to work with SQLModel model
    

# jwt token
class Token(BaseModel):
    access_token: str
    token_type: str


# data encoded in JWT
class TokenData(BaseModel):
    email: str | None = None

# photo for public
class PhotoPublic(BaseModel):
    id: int
    filename: str
    user_id: int
    version: int



## image transformation

class Resize(BaseModel):
    width: int
    height: int

class Crop(BaseModel):
    width: int
    height: int
    x: int
    y: int

class Filters(BaseModel):
    grayscale: bool

class Transformations(BaseModel):
    resize: Resize | None = None
    crop: Crop | None = None
    rotate: int | None = None
    format: str | None = None
    filters: Filters | None = None

class ImageTransformationsRequest(BaseModel):
    transformations: Transformations
