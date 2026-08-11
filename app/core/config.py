"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    APP_NAME: str = "RepoInfo API"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = Field(..., min_length=32)
    BACKEND_BASE_URL: AnyHttpUrl = Field(default="http://localhost:8000")
    FRONTEND_BASE_URL: AnyHttpUrl = Field(default="http://localhost:5173")
    # Environment files use comma-separated values. Disable pydantic-settings' JSON decoding so the validator below receives the raw string.
    ALLOWED_HOSTS: Annotated[list[str], NoDecode] = ["*"]
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # ---- Database ----
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "repoinfo"
    POSTGRES_PASSWORD: str = "repoinfo"
    POSTGRES_DB: str = "repoinfo"
    POSTGRES_SSL_MODE: Literal["disable", "require"] = "disable"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        url = (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
        if self.POSTGRES_SSL_MODE != "disable":
            url += f"?sslmode={self.POSTGRES_SSL_MODE}"
        return url

    # ---- Redis ----
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_CACHE_DB: int = 0
    REDIS_CELERY_BROKER_DB: int = 1
    REDIS_CELERY_BACKEND_DB: int = 2
    REDIS_RATE_LIMIT_DB: int = 3

    def _redis_url(self, db: int) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{db}"

    @property
    def REDIS_CACHE_URL(self) -> str:
        return self._redis_url(self.REDIS_CACHE_DB)

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self._redis_url(self.REDIS_CELERY_BROKER_DB)

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self._redis_url(self.REDIS_CELERY_BACKEND_DB)

    @property
    def RATE_LIMIT_REDIS_URL(self) -> str:
        return self._redis_url(self.REDIS_RATE_LIMIT_DB)

    # ---- JWT / Auth ----
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_REMEMBER_ME_REFRESH_DAYS: int = 90
    JWT_ISSUER: str = "repoinfo-api"
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6

    # ---- OAuth ----
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/github/callback"

    # ---- Rate limiting ----
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_AI: str = "30/minute"

    # ---- Object storage (S3-compatible) ----
    AWS_ENDPOINT_URL_S3: str = "http://localhost:9000"
    AWS_ACCESS_KEY_ID: str = "repoinfo_admin"
    AWS_SECRET_ACCESS_KEY: str = "repoinfo_secret_key"
    AWS_REGION: str = "us-east-1"
    STORAGE_BUCKET: str = "repoinfo"
    STORAGE_PRESIGNED_URL_EXPIRE_SECONDS: int = 3600

    # ---- Elasticsearch ----
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ELASTICSEARCH_USERNAME: str | None = None
    ELASTICSEARCH_PASSWORD: str | None = None
    ELASTICSEARCH_REPO_INDEX: str = "repositories"
    ELASTICSEARCH_FILE_INDEX: str = "repository_files"
    ELASTICSEARCH_FUNCTION_INDEX: str = "repository_functions"

    # ---- Milvus ----
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_COLLECTION_CHUNKS: str = "code_chunks"
    MILVUS_COLLECTION_FILES: str = "file_embeddings"
    MILVUS_COLLECTION_DOCS: str = "doc_embeddings"
    EMBEDDING_DIMENSION: int = 1536

    # ---- AI providers ----
    DEFAULT_AI_PROVIDER: Literal["gemini", "openai", "claude", "openrouter", "ollama"] = "claude"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    AI_MAX_CONTEXT_TOKENS: int = 128_000
    AI_DEFAULT_TEMPERATURE: float = 0.3
    AI_STREAM_CHUNK_TIMEOUT_SECONDS: int = 60
    # Providers tried in order when the active one reports its quota/credit is exhausted.
    AI_PROVIDER_FALLBACK_ORDER: Annotated[list[str], NoDecode] = ["openai", "openrouter"]

    # ---- Email (SMTP) ----
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    EMAIL_FROM_ADDRESS: str = "noreply@repoinfo.dev"
    EMAIL_FROM_NAME: str = "RepoInfo"

    # ---- Billing (Stripe-compatible) ----
    STRIPE_API_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_PRO: str = ""
    STRIPE_PRICE_ID_TEAM: str = ""

    # ---- Observability ----
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    PROMETHEUS_ENABLED: bool = True

    # ---- Repository analysis ----
    REPO_CLONE_MAX_SIZE_MB: int = 500
    REPO_CLONE_TIMEOUT_SECONDS: int = 300
    REPO_CLONE_WORKDIR: str = "/tmp/repoinfo/clones"
    REPO_MAX_FILE_SIZE_BYTES: int = 2_000_000

    # ---- API key encryption ----
    API_KEY_ENCRYPTION_SECRET: str = Field(..., min_length=32)

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", "AI_PROVIDER_FALLBACK_ORDER", mode="before")
    @classmethod
    def _split_csv(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
