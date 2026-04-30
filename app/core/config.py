from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pro E-commerce API"

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REDIS_HOST: str
    REDIS_PORT: int = 6379  # Default Redis port
    REDIS_PASSWORD: str | None = None

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool
    EMAIL_VERIFY_BASE_URL: str = "http://localhost:8001"
    RAZORPAY_KEY_ID: str
    RAZORPAY_SECRET_KEY: str
    RAZORPAY_WEBHOOK_SECRET: str

    model_config = SettingsConfigDict(env_file=".env.docker")


settings = Settings()
