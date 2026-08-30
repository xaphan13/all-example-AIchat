from pydantic_settings import BaseSettings, SettingsConfigDict


class Setting(BaseSettings):
    """
    Application settings configuration.
    """

    # Database connection string
    DATABASE_URL: str = "sqlite+aiosqlite:///./sqlite.db"

    # GitHub token for API access
    GITHUB_TOKEN: str = ""

    # JWT secret key
    SECRET: str = "your-secret-key-change-this-in-production"

    # Debug mode flag
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )


settings = Setting()
