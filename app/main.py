from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agent import router as agent_router
from app.api.routes.runs import router as runs_router
from app.mock_business_api import router as mock_router


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mock_router)
app.include_router(agent_router)
app.include_router(runs_router)


@app.get("/")
def home():
    return {
        "message": "Quality Agent API is running.",
    }
