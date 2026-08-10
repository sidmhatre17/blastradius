from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://blastradius:blastradius@localhost:5432/blastradius"
    redis_url: str = "redis://localhost:6379/0"
    app_mode: str = "local"  # local | ci | cloud
    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5:7b-instruct"
    ollama_base_url: str = "http://127.0.0.1:11434"
    vector_backend: str = "chroma"
    chroma_path: str = "./data/chroma"
    repos_path: str = "./data/repos"
    sample_root: str = "./data"
    api_key: str = "dev-secret"
    log_level: str = "INFO"
    embed_dim: int = 384


def get_settings() -> Settings:
    return Settings()
