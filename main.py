# main.py
from routes import chat
from fastapi import FastAPI
from routes import auth  # или как ты там назвал
from routes import admin
from fastapi.middleware.cors import CORSMiddleware
from routes.storage import router as storage_router
from routes import title_generator  # если есть роуты для title
from routes import chart_generator
from routes import favourites

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или ["*"] для всех, но лучше явно
    allow_credentials=True,
    allow_methods=["*"],  # разрешить все методы, включая OPTIONS
    allow_headers=["*"],
)


# Роуты
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(storage_router)
app.include_router(title_generator.router)  # если есть роуты для title
app.include_router(chart_generator.router)  # если есть роуты для title
app.include_router(favourites.router)