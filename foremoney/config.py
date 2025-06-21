from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
import os


@dataclass
class Settings:
    token: str
    database_path: Path


load_dotenv()

def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN is not set")
    db_path = Path(os.getenv("DATABASE_PATH", "db.sqlite3"))
    return Settings(token=token, database_path=db_path)
