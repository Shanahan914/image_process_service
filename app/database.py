from decouple import config
from sqlmodel import Session, SQLModel, create_engine
from typing import Annotated
from fastapi import Depends


owner = config('OWNER')
password = config('PG_PASSWORD')
POSTGRES_DATABASE_URL = f'postgresql://{owner}:{password}@db:5432/image_processing'
engine = create_engine(POSTGRES_DATABASE_URL)


# creates the tables
def create_db_and_tables():
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        print(f'error: {e}')


# produces a session for each db request
def get_session():
    with Session(engine) as session:
        yield session


# annotated is from typing to add metadata to a type. 
# Session handles the db request and get_session is added as a dependeny.
# we then use SessionDep when we need to reference the db session. 
# we will add this to routes. 
SessionDep = Annotated[Session, Depends(get_session)]

