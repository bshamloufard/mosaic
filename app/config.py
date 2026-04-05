from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Linq
    linq_api_token: str
    linq_phone_number: str
    linq_webhook_secret: str
    linq_base_url: str = "https://api.linqapp.com/api/partner/v3"

    # Anthropic
    anthropic_api_key: str

    # Google
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    # Supabase
    supabase_url: str
    supabase_service_key: str

    # App
    app_base_url: str
    default_timezone: str = "America/Los_Angeles"

    class Config:
        env_file = ".env"


settings = Settings()
