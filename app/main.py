from fastapi import FastAPI
from .database import  create_db_and_tables
from .routes import router as all_routes


app = FastAPI()

app.include_router(all_routes)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
async def root():
    return {"message": "hello world"}
