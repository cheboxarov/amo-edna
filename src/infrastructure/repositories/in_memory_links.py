from use_cases import ConversationLinkRepository
from domain.models import ConversationLink, MessageLink


class InMemoryConversationLinkRepository(ConversationLinkRepository):
	def __init__(self):
		self._links: dict[str, str] = {}  # amocrm_chat_id <-> edna_conversation_id

	async def get_edna_conversation_id(self, amocrm_chat_id: str) -> str | None:
		return self._links.get(amocrm_chat_id)

	async def get_amocrm_chat_id(self, edna_conversation_id: str) -> str | None:
		# Для двунаправленного поиска
		for amocrm_id, edna_id in self._links.items():
			if edna_id == edna_conversation_id:
				return amocrm_id
		return None

	async def save_link(self, link: ConversationLink) -> None:
		self._links[link.amocrm_chat_id] = link.edna_conversation_id


class InMemoryMessageLinkRepository:
	def __init__(self):
		self._links: dict[str, MessageLink] = {}  # source_message_id -> MessageLink

	async def get_link_by_source_id(self, source_message_id: str) -> MessageLink | None:
		return self._links.get(source_message_id)

	async def save_link(self, link: MessageLink) -> None:
		self._links[link.source_message_id] = link