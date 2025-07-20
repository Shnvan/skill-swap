# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from .routes import users, ratings, reports, task

app = FastAPI(
    title="SkillSwap API",
    version="1.0.0",
    description="PUP SkillSwap"
)

# --------------------
# MIDDLEWARES (CORS)
# --------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------
# INCLUDE ROUTERS
# --------------------
app.include_router(users.router)
app.include_router(ratings.router)
app.include_router(reports.router)
app.include_router(task.router)

# --------------------
# ROOT + HEALTH
# --------------------
@app.get("/")
async def root():
    return {"message": "Welcome to the SkillSwap API!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)


app.include_router(task.router, prefix="/tasks", tags=["Tasks"])
