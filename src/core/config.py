from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv, find_dotenv

# Ensure .env is loaded regardless of current working directory
load_dotenv(find_dotenv(), override=False)


class EdnaSettings(BaseSettings):
	model_config = SettingsConfigDict(env_prefix="EDNA_")
	api_key: str = "your_edna_api_key"
	base_url: str = "https://app.edna.ru"
	im_type: str = "whatsapp"
	send_path: str = "/api/cascade/schedule"
	callback_path: str = "/api/callback/set"
	subject_id: int | None = None
	cascade_id: str | None = None
	subscriber_id_type: str = "PHONE"
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

	# Настройки создания чатов
	auto_create_chats: bool = True
	default_chat_source_external_id: str = ""

	# Настройки источников
	auto_create_sources: bool = True
	tema_edna_source_name: str = "TeMa Edna"
	source_pipeline_id: Optional[int] = None  # AMOCRM_SOURCE_PIPELINE_ID - ID воронки для создания источников
	source_external_id_prefix: str = "tema_edna"


class DatabaseSettings(BaseSettings):
	model_config = SettingsConfigDict(env_prefix="APP_")
	url: str = "sqlite+aiosqlite:///data/app.db"
	use_sqlalchemy_repos: bool = True

class AppSettings(BaseSettings):
	model_config = SettingsConfigDict(env_prefix="APP_")
	public_base_url: str | None = None
	enable_media_proxy: bool = True


class Settings(BaseSettings):
	edna: EdnaSettings = EdnaSettings()
	amocrm: AmoCrmSettings = AmoCrmSettings()
	app: AppSettings = AppSettings()
	database: DatabaseSettings = DatabaseSettings()


settings = Settings()
