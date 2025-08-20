from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv, find_dotenv

# Ensure .env is loaded regardless of current working directory
load_dotenv(find_dotenv(), override=False)


class EdnaSettings(BaseSettings):
	model_config = SettingsConfigDict(env_prefix="EDNA_")
	api_key: str = "your_edna_api_key"
	base_url: str = "https://app.edna.ru"
	im_type: str = "whatsapp"
	send_path: str = "/api/messages/send"
	callback_path: str = "/api/callback/set"
	subject_id: int | None = None
	status_callback_url: str | None = None
	in_message_callback_url: str | None = None
	message_matcher_callback_url: str | None = None


class AmoCrmSettings(BaseSettings):
	model_config = SettingsConfigDict(env_prefix="AMOCRM_")
	base_url: str = "https://your_subdomain.amocrm.ru"
	token: str = "your_amocrm_token"
	amojo_base_url: str = "https://amojo.amocrm.ru"
	scope_id: str = ""
	channel_id: str = ""
	account_id: str = ""
	channel_secret: str = "your_channel_secret"
	connect_title: str = "Integration Channel"
	hook_api_version: str = "v2"


class Settings(BaseSettings):
	edna: EdnaSettings = EdnaSettings()
	amocrm: AmoCrmSettings = AmoCrmSettings()


settings = Settings()
