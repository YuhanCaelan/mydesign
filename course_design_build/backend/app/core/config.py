"""集中读取环境变量，避免数据库地址、密钥散落在业务代码中。"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "慧医云课程设计版"
    database_url: str = "mysql+pymysql://medical_user:Medical123%21@127.0.0.1:3306/smart_medical?charset=utf8mb4"
    jwt_secret: str = "course-design-change-this-secret-key"
    jwt_expire_minutes: int = 120
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
