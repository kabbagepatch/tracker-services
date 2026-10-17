
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
  frontend_url: str = 'http://localhost:5173'
  google_application_credentials: SecretStr
  discogs_key: SecretStr
  discogs_secret: SecretStr

  model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
