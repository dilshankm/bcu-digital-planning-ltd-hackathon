"""Service for managing multi-turn conversation state"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid


class ConversationService:
    """In-memory conversation state management (can be replaced with DynamoDB/Redis)"""
    
    def __init__(self):
        # In-memory storage: session_id -> conversation history
        self.conversations: Dict[str, Dict] = {}
        # Clean up old conversations after 24 hours
        self.expiry_hours = 24
    
    def create_session(self) -> str:
        """Create a new conversation session"""
        session_id = str(uuid.uuid4())
        self.conversations[session_id] = {
            "session_id": session_id,
            "created_at": datetime.now(),
            "messages": [],
            "last_updated": datetime.now()
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get conversation history for a session"""
        if session_id in self.conversations:
            session = self.conversations[session_id]
            # Check if expired
            if datetime.now() - session["created_at"] > timedelta(hours=self.expiry_hours):
                del self.conversations[session_id]
                return None
            return session
        return None
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a message to conversation history"""
        if session_id not in self.conversations:
            self.conversations[session_id] = {
                "session_id": session_id,
                "created_at": datetime.now(),
                "messages": [],
                "last_updated": datetime.now()
            }
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.conversations[session_id]["messages"].append(message)
        self.conversations[session_id]["last_updated"] = datetime.now()
    
    def get_conversation_context(self, session_id: str, max_messages: int = 10) -> str:
        """Get recent conversation context for LLM"""
        session = self.get_session(session_id)
        if not session or not session["messages"]:
            return ""
        
        # Get last N messages
        recent_messages = session["messages"][-max_messages:]
        context_parts = []
        for msg in recent_messages:
            role = msg["role"]
            content = msg["content"][:500]  # Truncate long messages
            context_parts.append(f"{role.upper()}: {content}")
        
        return "\n".join(context_parts)
    
    def cleanup_expired(self):
        """Remove expired conversations"""
        now = datetime.now()
        expired = [
            sid for sid, session in self.conversations.items()
            if now - session["created_at"] > timedelta(hours=self.expiry_hours)
        ]
        for sid in expired:
            del self.conversations[sid]


# Global instance
conversation_service = ConversationService()

