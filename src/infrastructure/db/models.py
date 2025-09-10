from sqlalchemy import Column, String, Text, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ConversationLinkORM(Base):
    """ORM модель для связей между чатами AmoCRM и Edna"""
    __tablename__ = "conversation_links"

    amocrm_chat_id = Column(String, primary_key=True, nullable=False)
    edna_conversation_id = Column(String, nullable=False)
    phone = Column(String, nullable=True)

    # Индекс для быстрого поиска по edna_conversation_id
    __table_args__ = (
        Index('idx_conversation_links_edna', 'edna_conversation_id'),
    )


class MessageLinkORM(Base):
    """ORM модель для связей между сообщениями"""
    __tablename__ = "message_links"

    source_message_id = Column(String, primary_key=True, nullable=False)
    source_provider = Column(String, nullable=False)
    target_provider = Column(String, nullable=False)
    target_message_id = Column(String, nullable=False)
    target_conversation_id = Column(String, nullable=False)
