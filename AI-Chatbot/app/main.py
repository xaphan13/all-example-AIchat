from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.v1.chat import router as bot_router
from app.api.v1.users import (
    current_user,
    fastapi_users,
    login_router,
    register_router,
    users_router,
)
from app.core.config import settings
from app.models.users import User

app = FastAPI()

# Serve static files and templates
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include API routes
app.include_router(bot_router, prefix="/api", tags=["api"])
app.include_router(login_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(register_router, prefix="/auth", tags=["auth"])


# HTML page routes
@app.get("/")
async def landing_page(request: Request):
    """Landing page"""
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/login")
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/signup")
async def signup_page(request: Request):
    """Signup page"""
    return templates.TemplateResponse("signup.html", {"request": request})


@app.get("/chat")
async def chat_page(request: Request, user: User = Depends(current_user)):
    """Chat interface (requires authentication)"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check(user: User = Depends(current_user)):
    """
    Health check endpoint to verify if the bot service is running.
    """
    return {"status": "ok"}
