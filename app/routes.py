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
import boto3
from decouple import config
from PIL import Image, ImageOps
import io

router = APIRouter()

ACCESS_TOKEN_EXPIRE_MINUTES = 30 
BUCKET_NAME = config('BUCKET_NAME')

s3 = boto3.client('s3')

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
@router.get("/users/")
def get_db(session: SessionDep) -> List[UserPublic]:
    data = session.exec(select(User)).all()
    return data


# /users 
# POST
# register endpoint
@router.post("/users/")
def create_user(user: UserInput, session: SessionDep) -> UserPublic:
    #get hashed password
    hashed_password = get_password_hash(user.plain_password)
    #create new User instance
    new_user = User(email = user.email, hashed_password=hashed_password)
    #add to db and commit
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return new_user


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
        print(f'error when uploading to s3:{e} ')

    # save to Photo table
    new_image = Photo(filename=file.filename, user_id = current_user.id, s3_uri = s3_uri)
    session.add(new_image)
    session.commit()
    session.refresh(new_image)
    return new_image


# /images 
# GET
# user can view text information about their uploaded images
@router.get("/images")
async def list_of_images(
            current_user: Annotated[User, Depends(get_current_user)],
            session: SessionDep) -> List[PhotoPublic]:
    photos = session.exec(select(Photo).where(Photo.user_id == current_user.id))
    return photos


# /images/id/transform POST

#helper function
def get_image_from_s3(object_key: str) -> Image.Image:
    # Retrieve the image from S3
    response = s3.get_object(Bucket=BUCKET_NAME, Key=object_key)
    image_data = response['Body'].read()  # Read the image data

    # Use BytesIO to load image with Pillow
    image = Image.open(io.BytesIO(image_data))
    return image

async def alter_image(im, img_request):
    print('now lets transform')
    transformation_dict = img_request.model_dump()
    transformations = transformation_dict['transformations']
    print(transformations)
    if transformations['resize'] is not None:
        width = transformations['resize']['width']
        height = transformations['resize']['height']
        im = im.resize((width, height))
    if transformations['crop'] is not None:
        width = transformations['crop']['width']
        height = transformations['crop']['height']
        x = transformations['crop']['x']
        y = transformations['crop']['y']
        im = im.crop(( x, y, x + width, y + height))
    if transformations['filters'] is not None:
        if transformations['filters']["grayscale"] == True:
            im = ImageOps.grayscale(im)
    if transformations['rotate'] is not None:
        degree = transformations['rotate']
        im = im.rotate(degree)
    if transformations['format'] is not None:
        format = transformations['format']
        im = im.save(im, format)
    return im

@router.post("/images/{image_id}/transform")
async def transform_image(image_id: int, 
                        img_request: ImageTransformationsRequest,
                        session: SessionDep) -> PhotoPublic:
    print('transform incoming')
    # get image metadata from db
    image_table_data = session.get(Photo, image_id)
    # get image from s3
    im = get_image_from_s3(image_table_data.s3_uri)
    # make the transformations
    new_im = await alter_image(im, img_request)
    # update metadata
    image_table_data.version = 2
    session.add(image_table_data)
    session.commit()
    session.refresh(image_table_data)
    return image_table_data


# /images/id GET
@router.get("/image/{image_id}")
async def get_image(image_id: int, session: SessionDep):
    image_table_data = session.get(Photo, image_id)
    s3_object = s3.get_object(Bucket=BUCKET_NAME, Key=image_table_data.s3_uri)
    return StreamingResponse(s3_object['Body'], media_type="image/jpeg")

