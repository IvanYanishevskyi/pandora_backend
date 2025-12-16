from dotenv import load_dotenv
import os

load_dotenv()

from routes import chat
from fastapi import FastAPI
from routes import auth
from routes import admin
from routes import sql_proxy
from fastapi.middleware.cors import CORSMiddleware
from routes.storage import router as storage_router
from routes import title_generator  
from routes import chart_generator
from routes import favourites
from routes import message_rating

app = FastAPI()


allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins != "*":
    allowed_origins = [origin.strip() for origin in allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)


# Роуты
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(sql_proxy.router)  
app.include_router(storage_router)
app.include_router(title_generator.router) 
app.include_router(chart_generator.router)  
app.include_router(favourites.router)
app.include_router(message_rating.router)