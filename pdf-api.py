from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Greeting(BaseModel):
    name: str

@app.get("/test/{name}")
def ping(name: str, DocEntry: str = None):
    return {"status": "ok", "name": name, "DocEntry": DocEntry}

@app.post("/greet")
def greet(payload: Greeting):
    return {"message": f"Hello, {payload.name}!"}
