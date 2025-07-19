# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import users, ratings, reports
import uvicorn
from .routes import users, ratings, reports, task

app = FastAPI(
    title="SkillSwap API",
    version="1.0.0",
    description="PUP SkillSwap"
)


# --------------------
# ROUTERS
# --------------------

app.include_router(users.router)
app.include_router(ratings.router)
app.include_router(reports.router)


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
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(ratings.router, prefix="/ratings", tags=["Ratings"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])

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
