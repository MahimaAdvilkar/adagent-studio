from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Project Blueprint",version="1.0.0")

class Msg(BaseModel):
    message: str

@app.get("/")
async def read_root():
    return {"message": "Backend is up and running!"}


@app.post("/createblueprint")
async def create_blueprint(payload: Msg):
    return {"message": payload.message}