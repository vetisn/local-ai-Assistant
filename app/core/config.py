# app/core/config.py
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Local AI Service"
    APP_VERSION: str = "1.0.0"

    DATABASE_URL: str = "sqlite:///./app.db"

    # 默认 Provider / 模型配置（全局兜底）
    AI_API_BASE: str = "https://api.openai.com/v1"
    AI_API_KEY: str = ""
    AI_MODEL: str = "gpt-4o-mini"
    AI_MODELS: str = "gpt-4o-mini"

    DEFAULT_SYSTEM_PROMPT: str = "You are a helpful AI assistant. Answer in Chinese."

    # 新增：Embedding 相关（用来生成向量）
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_MODELS: str = "text-embedding-3-small,text-embedding-3-large,text-embedding-ada-002"

    # 搜索API配置
    TAVILY_API_KEY: str = ""

    @property
    def embedding_models(self) -> List[str]:
        if not self.EMBEDDING_MODELS:
            return [self.EMBEDDING_MODEL]
        return [x.strip() for x in self.EMBEDDING_MODELS.split(",") if x.strip()]

    # 新增：知识库相关默认配置
    KNOWLEDGE_DEFAULT_KB_NAME: str = "default"
    KNOWLEDGE_DEFAULT_KB_DESCRIPTION: str = "Default knowledge base"

    @property
    def ai_models(self) -> List[str]:
        if not self.AI_MODELS:
            return [self.AI_MODEL]
        return [x.strip() for x in self.AI_MODELS.split(",") if x.strip()]


settings = Settings()
