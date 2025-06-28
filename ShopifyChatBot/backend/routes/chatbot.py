from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from utils.response_format import success_response, error_response
from typing import Optional

# Import shared instances from the new dependencies file
from dependencies import session_manager, agent_coordinator, guard_agent, order_agent

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()
# Remove local instantiations
# agent_coordinator = AgentCoordinator()
# session_manager = SessionManager()
# guard_agent = GuardAgent()
# order_agent = OrderAgent()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    confidence: float
    agent_used: str
    session_id: str
    history: list
    safety_check: Optional[dict] = None

class SafetyCheckRequest(BaseModel):
    message: str

class OrderRequest(BaseModel):
    message: str
    customer_id: Optional[str] = None

@router.post("/safety-check")
async def check_message_safety(request: SafetyCheckRequest):
    """
    Test endpoint to check message safety using the guard agent.
    """
    try:
        logger.info(f"Testing guard agent with message: {request.message}")
        result = await guard_agent.check_message(request.message)
        return success_response(
            data=result,
            message="Safety check completed successfully"
        )
    except Exception as e:
        logger.error(f"Error in safety check: {str(e)}")
        return error_response(
            message="Failed to perform safety check",
            error=str(e)
        )

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint that processes messages through the agent coordinator.
    """
    try:
        logger.debug(f"Received chat request: {request.message}")

        # Use the existing session or create a new one if it doesn't exist or is invalid
        session = session_manager.get_session(request.session_id)
        if not session:
            logger.warning(f"Session ID '{request.session_id}' not found or invalid. Creating a new session.")
            session_id = session_manager.create_session()
        else:
            session_id = session.session_id
        
        logger.info(f"Using session ID: {session_id}")

        # First, check message safety
        safety_result = await guard_agent.check_message(request.message)
        logger.info(f"Safety check result: {safety_result}")
        
        if not safety_result["is_safe"] or not safety_result["details"]["is_shopping_related"]:
            # Even for unsafe messages, we should use a valid session and record the interaction
            response_text = "I apologize, but I can only assist with shopping-related queries. Please ask me about products, orders, or shopping assistance."
            session_manager.add_message(session_id, "user", request.message)
            session_manager.add_message(session_id, "assistant", response_text)
            history = session_manager.get_history(session_id) or []
            
            return success_response(
                data={
                    "response": response_text,
                    "confidence": 1.0,
                    "agent_used": "guard",
                    "session_id": session_id,
                    "history": history,
                    "safety_check": safety_result
                },
                message="Message filtered by safety check"
            )
        
        # Add user message to history
        session_manager.add_message(session_id, "user", request.message)
        
        # Get history and customer info to pass to the agent
        history_before_processing = session_manager.get_history(session_id) or []
        customer_info = session_manager.get_customer_info(session_id) or {}

        # Process the message through the agent coordinator
        agent_response = await agent_coordinator.process_message(
            request.message, 
            history=history_before_processing,
            customer_info=customer_info
        )
        
        # Add bot response to history
        session_manager.add_message(
            session_id, 
            "assistant", 
            agent_response["response"],
            metadata={"agent": agent_response["agent_used"]}
        )
        
        # Get final updated chat history
        final_history = session_manager.get_history(session_id) or []
        
        # Create the response object
        response = ChatResponse(
            response=agent_response["response"],
            confidence=agent_response["confidence"],
            agent_used=agent_response["agent_used"],
            session_id=session_id,
            history=final_history,
            safety_check=safety_result
        )
        
        # Return using the success response format
        return success_response(
            data=response.dict(),
            message="Message processed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        # It's better to use exc_info=True for full traceback in logs
        return error_response(
            message="Failed to process chat request",
            error=str(e)
        )

@router.get("/session/{session_id}")
async def get_session_history(session_id: str):
    """Get chat history for a session"""
    logger.info(f"Getting history for session: {session_id}")
    history = session_manager.get_history(session_id)
    if history is None:
        return error_response(
            message="Session not found",
            error=f"Session {session_id} does not exist"
        )
    return success_response(
        data={"history": history},
        message="Session history retrieved successfully"
    )

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session"""
    logger.info(f"Attempting to delete session: {session_id}")
    if session_manager.delete_session(session_id):
        return success_response(
            message="Session deleted successfully"
        )
    return error_response(
        message="Session not found",
        error=f"Session {session_id} does not exist"
    )

@router.get("/sessions")
async def list_sessions():
    """List all active sessions"""
    logger.info("Listing all active sessions")
    return success_response(
        data={"sessions": list(session_manager.sessions.keys())},
        message="Active sessions retrieved successfully"
    )

@router.post("/test-order")
async def test_order_agent(request: OrderRequest):
    """
    Test endpoint for the OrderAgent.
    """
    try:
        logger.info(f"Testing OrderAgent with message: {request.message}")
        result = await order_agent.process_order_request(request.message, request.customer_id)
        return success_response(
            data=result,
            message="Order request processed successfully"
        )
    except Exception as e:
        logger.error(f"Error in order processing: {str(e)}")
        return error_response(
            message="Failed to process order request",
            error=str(e)
        )
