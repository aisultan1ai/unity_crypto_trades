from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.binance_trades import router as binance_router
from app.core.config import get_settings

settings = get_settings()
print("DATABASE_URL RAW:", repr(settings.database_url))
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(binance_router)


@app.get("/health")
def health():
    return {"status": "ok"}