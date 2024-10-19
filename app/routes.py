from fastapi import APIRouter, Query, Path, HTTPException, UploadFile, File, Depends, status
from starlette.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated, List
from sqlmodel import select
from datetime import timedelta
from .database import SessionDep
from .schemas import  Token, UserPublic, UserInput, PhotoPublic, ImageTransformationsRequest
from .models import User, Photo
from .auth import get_password_hash, authenticate_user, create_access_token, get_current_user
from .tasks import generate_unique_filename
from .rabbitmq_publisher import send_transformation_task
import boto3
from decouple import config
from PIL import Image, ImageOps
import io
import logging
from fastapi_limiter.depends import RateLimiter

router = APIRouter()

ACCESS_TOKEN_EXPIRE_MINUTES = 30 
BUCKET_NAME = config('BUCKET_NAME')
REGION = config('REGION')
AWS_SECRET = config('AWS_SECRET')
AWS_PUBLIC = config('AWS_PUBLIC')

s3 = boto3.client('s3', region_name = REGION, aws_secret_access_key = AWS_SECRET, aws_access_key_id=AWS_PUBLIC)

# initialize logger 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# error handler and logger
def log_and_raise_error(message: str, status_code: int = 500):
    logger.error(message)
    raise HTTPException(status_code=status_code, detail=message)

# /token 
# POST
# login endpoint
@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
) -> Token:
    print( form_data.username)
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


# /users 
# GET
# login endpoint
# @router.get("/users/")
# def get_db(session: SessionDep,) -> List[UserPublic]:
#     data = session.exec(select(User)).all()
#     return data


# /users 
# POST
# register endpoint
@router.post("/users/")
def create_user(user: UserInput, session: SessionDep) -> UserPublic:
    #get hashed password
    try:
        hashed_password = get_password_hash(user.plain_password)
    except Exception as e:
        log_and_raise_error(f"Error hashing password: {e}", 400)
    
    #create new User instance
    try: 
        new_user = User(email = user.email, hashed_password=hashed_password)
        #add to db and commit
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return new_user
    except Exception as e:
        log_and_raise_error(f"Error adding user to db: {e}", 400)


# get current user - test route
@router.get("/users/me/", response_model=UserPublic)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return current_user


# /images 
# POST
# user uploads an image
@router.post("/images")
async def create_upload_file(file: UploadFile,
            current_user: Annotated[User, Depends(get_current_user)],
            session: SessionDep) -> PhotoPublic:
    
    ### upload to S3
    try:
        s3_uri = generate_unique_filename(file.filename)
        s3.upload_fileobj(file.file, BUCKET_NAME, s3_uri)
    except Exception as e:
        log_and_raise_error(f"error uploading image to cloud: {e}", 500)

    # save to Photo table
    try:
        new_image = Photo(filename=file.filename, user_id = current_user.id, s3_uri = s3_uri)
        session.add(new_image)
        session.commit()
        session.refresh(new_image)
        return new_image
    except Exception as e:
        log_and_raise_error(f"Error saving image metadata to db: {e}", 500)


# /images 
# GET
# user can view text information about their uploaded images
@router.get("/images")
async def list_of_images(
            current_user: Annotated[User, Depends(get_current_user)],
            session: SessionDep,
            skip: int = Query(0, ge=0), # skip and limit for pagination
            limit: int = Query(10, ge=1),
            q: str = Query(None, description='search filename including extension')) -> List[PhotoPublic]:
    try:
        query_selection = select(Photo).where(Photo.user_id == current_user.id)
        if q:
            query_selection =  query_selection.where(Photo.filename.ilike(f"%{q}%"))
        photos = session.exec(query_selection.offset(skip).limit(limit)).all()
        return photos
    except Exception as e:
        log_and_raise_error(f"Error retreiving metadata of the images: {e}")


# /images/id/transform POST

#helper function
def get_image_from_s3(object_key: str) -> Image.Image:
    # Retrieve the image from S3
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=object_key)
        image_data = response['Body'].read()  # Read the image data
        image = Image.open(io.BytesIO(image_data))
        return image
    except Exception as e:
        log_and_raise_error(f"Error retreiving image from cloud: {e}")
    
# route
@router.post("/images/{image_id}/transform")
async def transform_image(image_id: int, 
                        img_request: ImageTransformationsRequest,
                        session: SessionDep,
                        current_user: Annotated[User, Depends(get_current_user)]) -> PhotoPublic:
    # get image metadata from db
    try:
        image_table_data = session.get(Photo, image_id)
    except Exception as e:
        log_and_raise_error(f"Error retreiving metadata of the image: {e}")
    if image_table_data.user_id != current_user.id:
        log_and_raise_error(f"You are not authorised to access this object", 403)
    # make the transformations
    try:
        transformation_dict = img_request.model_dump()
        send_transformation_task(image_id, transformation_dict, image_table_data.s3_uri)
    except Exception as e:
        log_and_raise_error(f"Error when transforming image. Logged from routes: {e}")
    # update metadata
    try:
        image_table_data.version = int( image_table_data.version) +1
        session.add(image_table_data)
        session.commit()
        session.refresh(image_table_data)
        return image_table_data
    except Exception as e:
        log_and_raise_error(f"Error saving image metadata to db: {e}", 500)
    

# /images/id GET
@router.get("/image/{image_id}")
async def get_image(image_id: int, 
                    session: SessionDep,
                    current_user: Annotated[User, Depends(get_current_user)]):
    try:
        image_table_data = session.get(Photo, image_id)
    except Exception as e:
        log_and_raise_error(f"Error retreiving metadata of the image: {e}")
    if image_table_data.user_id != current_user.id:
        log_and_raise_error(f"You are not authorised to access this object", 403)
    try:
        s3_object = s3.get_object(Bucket=BUCKET_NAME, Key=image_table_data.s3_uri)
    except Exception as e:
        log_and_raise_error(f"Error retreiving image from cloud: {e}", 500)
    return StreamingResponse(s3_object['Body'], media_type="image/jpeg")

