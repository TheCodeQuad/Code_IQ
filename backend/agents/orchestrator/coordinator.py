"""
Agent Coordinator
Handles agent communication and coordination
"""
from typing import Dict, Any, List
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class AgentCoordinator:
    """Coordinates communication between agents"""
    
    def __init__(self):
        self.logger = get_logger("coordinator")
        self.message_queue = []
    
    def send_message(self, from_agent: str, to_agent: str, message: Any):
        """Send message from one agent to another"""
        self.message_queue.append({
            'from': from_agent,
            'to': to_agent,
            'message': message
        })
        self.logger.debug(f"Message: {from_agent} -> {to_agent}")
    
    def get_messages(self, agent_name: str) -> List[Any]:
        """Get messages for specific agent"""
        messages = [
            msg['message'] for msg in self.message_queue
            if msg['to'] == agent_name
        ]
        
        # Clear retrieved messages
        self.message_queue = [
            msg for msg in self.message_queue
            if msg['to'] != agent_name
        ]
        
        return messages