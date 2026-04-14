from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "jrnys"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Mammoth
    mammoth_api_base_url: str = ""
    mammoth_api_login_email: str = ""
    mammoth_api_login_password: str = ""
    mammoth_data_save_delay: int = 5        # seconds
    mammoth_lab_results_delay: int = 10     # seconds
    mammoth_lab_results_patient_delay: int = 180  # seconds

    # Quest Booking
    quest_booking_base_url: str = ""
    quest_booking_authorization_token: str = ""
    quest_booking_secret: str = ""

    # Quest Orders
    quest_orders_base_url: str = ""
    quest_client_id: str = ""
    quest_client_secret: str = ""
    quest_zip_search_radius_meters: int = 16000

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    aws_s3_bucket: str = "jrnys-quest-docs"

    # Auth
    jwt_secret: str = "changeme"


settings = Settings()
