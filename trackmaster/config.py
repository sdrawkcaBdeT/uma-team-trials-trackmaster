# trackmaster/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DISCORD_BOT_TOKEN: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    DB_NAME: str = "umamusume"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()