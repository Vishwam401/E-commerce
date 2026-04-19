from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pro E-commerce API"

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REDIS_HOST: str
    REDIS_PORT: int = 6379  # Default Redis port



    model_config = SettingsConfigDict(env_file=".env.docker")


settings = Settings()
