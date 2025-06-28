from session_manager import SessionManager
from agents.agent_coordinator import AgentCoordinator
from agents.guard_agent import GuardAgent
from agents.order_agent import OrderAgent

# Create single, shared instances of services
session_manager = SessionManager()
agent_coordinator = AgentCoordinator()
guard_agent = GuardAgent()
order_agent = OrderAgent() 