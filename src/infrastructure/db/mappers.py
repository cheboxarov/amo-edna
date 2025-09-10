from domain.models import ConversationLink, MessageLink
from .models import ConversationLinkORM, MessageLinkORM


def to_conversation_link_model(orm: ConversationLinkORM) -> ConversationLink:
    """Преобразует ORM модель в доменную модель ConversationLink"""
    return ConversationLink(
        amocrm_chat_id=orm.amocrm_chat_id,
        edna_conversation_id=orm.edna_conversation_id,
    )


def to_conversation_link_orm(domain: ConversationLink) -> ConversationLinkORM:
    """Преобразует доменную модель в ORM модель ConversationLinkORM"""
    return ConversationLinkORM(
        amocrm_chat_id=domain.amocrm_chat_id,
        edna_conversation_id=domain.edna_conversation_id,
    )


def to_message_link_model(orm: MessageLinkORM) -> MessageLink:
    """Преобразует ORM модель в доменную модель MessageLink"""
    return MessageLink(
        source_provider=orm.source_provider,
        source_message_id=orm.source_message_id,
        target_provider=orm.target_provider,
        target_message_id=orm.target_message_id,
        target_conversation_id=orm.target_conversation_id,
    )


def to_message_link_orm(domain: MessageLink) -> MessageLinkORM:
    """Преобразует доменную модель в ORM модель MessageLinkORM"""
    return MessageLinkORM(
        source_message_id=domain.source_message_id,
        source_provider=domain.source_provider,
        target_provider=domain.target_provider,
        target_message_id=domain.target_message_id,
        target_conversation_id=domain.target_conversation_id,
    )
