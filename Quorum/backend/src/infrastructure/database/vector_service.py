"""
Vector embedding service for generating and managing embeddings.
Integrates with OpenAI's embedding API.
"""
import logging
from typing import List, Optional, Tuple
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from .models import Message, Embedding
from .repository import EmbeddingRepository, MessageRepository, ConversationRepository
from ...core.config import settings

logger = logging.getLogger(__name__)


class VectorService:
    """Service for managing vector embeddings."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize vector service with OpenAI client."""
        self.client = AsyncOpenAI(
            api_key=openai_api_key or settings.openai_api_key
        )
        self.model = settings.embedding_model
        self.dimension = settings.embedding_dimension
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using OpenAI.
        
        Args:
            text: Text to embed
        
        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            
            return response.data[0].embedding
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def embed_message(
        self,
        session: AsyncSession,
        message: Message,
    ) -> Embedding:
        """
        Generate and store embedding for a message.
        
        Args:
            session: Database session
            message: Message to embed
        
        Returns:
            Created Embedding object
        """
        # Generate embedding
        embedding_vector = await self.generate_embedding(message.content)
        
        # Store embedding
        embedding = await EmbeddingRepository.create(
            session=session,
            conversation_id=message.conversation_id,
            message_id=message.id,
            embedding=embedding_vector,
            text_content=message.content,
            model=self.model,
            metadata={
                "role": message.role,
                "agent_id": message.agent_id,
                "agent_type": message.agent_type,
            }
        )
        
        return embedding
    
    async def embed_text(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        text: str,
        metadata: Optional[dict] = None,
    ) -> Embedding:
        """
        Generate and store embedding for arbitrary text.
        
        Args:
            session: Database session
            conversation_id: Associated conversation ID
            text: Text to embed
            metadata: Optional metadata
        
        Returns:
            Created Embedding object
        """
        embedding_vector = await self.generate_embedding(text)
        
        embedding = await EmbeddingRepository.create(
            session=session,
            conversation_id=conversation_id,
            embedding=embedding_vector,
            text_content=text,
            model=self.model,
            metadata=metadata or {},
        )
        
        return embedding
    
    async def search_similar_messages(
        self,
        session: AsyncSession,
        query: str,
        limit: int = 10,
        threshold: Optional[float] = None,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> List[Tuple[Message, float]]:
        """
        Search for messages similar to the query text.
        
        Args:
            session: Database session
            query: Query text
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            conversation_id: Optional filter by conversation
        
        Returns:
            List of (Message, similarity_score) tuples
        """
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)
        
        # Search for similar embeddings
        similar_embeddings = await EmbeddingRepository.similarity_search(
            session=session,
            query_embedding=query_embedding,
            limit=limit,
            threshold=threshold,
            conversation_id=conversation_id,
        )
        
        # Get associated messages
        results = []
        for embedding, similarity in similar_embeddings:
            if embedding.message_id:
                message = await MessageRepository.get_by_id(
                    session=session,
                    message_id=embedding.message_id,
                )
                if message:
                    results.append((message, similarity))
        
        return results
    
    async def search_similar_conversations(
        self,
        session: AsyncSession,
        query: str,
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> List[Tuple[uuid.UUID, str, float]]:
        """
        Search for conversations similar to the query text.
        
        Args:
            session: Database session
            query: Query text
            limit: Maximum number of results
            threshold: Minimum similarity threshold
        
        Returns:
            List of (conversation_id, title, similarity_score) tuples
        """
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)
        
        # Search for similar conversations
        similar_conversations = await EmbeddingRepository.search_conversations(
            session=session,
            query_embedding=query_embedding,
            limit=limit,
            threshold=threshold,
        )
        
        return [
            (conv.id, conv.title or "Untitled", similarity)
            for conv, similarity in similar_conversations
        ]
    
    async def get_conversation_context(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        current_message: str,
        context_limit: int = 5,
    ) -> List[Message]:
        """
        Get relevant context messages from a conversation based on similarity.
        Useful for providing context to LLMs.
        
        Args:
            session: Database session
            conversation_id: Conversation to search within
            current_message: Current message to find context for
            context_limit: Maximum number of context messages
        
        Returns:
            List of relevant messages ordered by sequence
        """
        similar_messages = await self.search_similar_messages(
            session=session,
            query=current_message,
            limit=context_limit,
            conversation_id=conversation_id,
        )
        
        # Extract messages and sort by sequence
        messages = [msg for msg, _ in similar_messages]
        messages.sort(key=lambda m: m.sequence_number)
        
        return messages

