from typing import Dict, List, Optional
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class ChatSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.messages: List[Dict] = []
        self.last_updated = datetime.now()
        self.customer_info = {
            "name": None,
            "email": None,
            "last_order": None
        }
        logger.info(f"Created new ChatSession with ID: {session_id}")

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.messages.append(message)
        self.last_updated = datetime.now()
        logger.debug(f"Added message to session {self.session_id}: {role} - {content[:50]}...")
        return message

    def update_customer_info(self, name: Optional[str] = None, email: Optional[str] = None, last_order: Optional[Dict] = None):
        if name:
            self.customer_info["name"] = name
        if email:
            self.customer_info["email"] = email
        if last_order:
            self.customer_info["last_order"] = last_order
        logger.debug(f"Updated customer info for session {self.session_id}: {self.customer_info}")

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        logger.info("SessionManager initialized with 0 sessions")

    def create_session(self) -> str:
        """Create a new chat session and return its ID"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = ChatSession(session_id)
        logger.info(f"Created new session: {session_id}. Total sessions: {len(self.sessions)}")
        return session_id

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a session by ID"""
        session = self.sessions.get(session_id)
        if session:
            logger.debug(f"Found session: {session_id}")
        else:
            logger.warning(f"Session not found: {session_id}. Available sessions: {list(self.sessions.keys())}")
        return session

    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> Optional[Dict]:
        """Add a message to a session"""
        session = self.get_session(session_id)
        if session:
            message = session.add_message(role, content, metadata)
            logger.debug(f"Added message to session {session_id}")
            return message
        logger.error(f"Cannot add message: Session {session_id} not found")
        return None

    def get_history(self, session_id: str) -> Optional[List[Dict]]:
        """Get chat history for a session"""
        session = self.get_session(session_id)
        if session:
            logger.debug(f"Retrieved history for session {session_id}: {len(session.messages)} messages")
            return session.messages
        logger.warning(f"Cannot get history: Session {session_id} not found")
        return None

    def get_customer_info(self, session_id: str) -> Optional[Dict]:
        """Get customer information for a session"""
        session = self.get_session(session_id)
        if session:
            return session.customer_info
        return None

    def update_customer_info(self, session_id: str, name: Optional[str] = None, email: Optional[str] = None, last_order: Optional[Dict] = None) -> bool:
        """Update customer information for a session"""
        session = self.get_session(session_id)
        if session:
            session.update_customer_info(name, email, last_order)
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}. Remaining sessions: {len(self.sessions)}")
            return True
        logger.warning(f"Cannot delete: Session {session_id} not found")
        return False 