
from typing import Annotated
from fastapi import Depends, HTTPException, status
from decouple import config
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from datetime import datetime, timedelta, timezone
import jwt
from jwt.exceptions import InvalidTokenError
from .schemas import Token, TokenData, UserPrivate
from .database import SessionDep
from .models import User

# constants for JWT
SECRET_KEY = config('SECRET_KEY')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 

# outh2 scheme for token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=['bcrypt'], deprecated="auto")


# verify password
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# hash password
def get_password_hash(password: str) -> str:
    print('hased', pwd_context.hash(password))
    return pwd_context.hash(password)


# get user from db
def get_user(session: SessionDep, email: str) -> UserPrivate | None:
    result = session.exec(select(User).where(User.email == email))
    user = result.first()
    if user:
        return UserPrivate.from_orm(user)
    return None
    

# authenticate user
def authenticate_user(session: SessionDep, email: str, password: str) -> UserPrivate | None:
    user = get_user(session, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


# creates the JWT access token
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# checks that the token includes the email 
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: SessionDep):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


