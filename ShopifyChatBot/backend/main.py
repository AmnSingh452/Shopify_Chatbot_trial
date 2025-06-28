from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from routes.chatbot import router as chatbot_router
import logging
import time
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import shared instances from the new dependencies file
from dependencies import session_manager, agent_coordinator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Shopify Chatbot API")

# Configure CORS with more permissive settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include routers
app.include_router(chatbot_router, prefix="/api")

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponseData(BaseModel):
    response: str
    session_id: str
    intent: Dict[str, Any]
    history: list
    customer_info: Optional[Dict[str, Any]] = None

class ApiResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[ChatResponseData] = None

class CustomerInfoUpdate(BaseModel):
    session_id: str
    name: Optional[str] = None
    email: Optional[str] = None

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Request to {request.url.path} took {process_time:.2f} seconds")
    return response

@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Welcome to Shopify Chatbot API"}

@app.get("/ping")
async def ping():
    logger.info("Ping endpoint called")
    return {"message": "pong"}

@app.post("/api/chat", response_model=ApiResponse)
async def chat(request: ChatRequest):
    try:
        logger.info(f"Received chat request. Session ID: {request.session_id}")

        # Use the existing session or create a new one if it doesn't exist or is invalid
        session = session_manager.get_session(request.session_id)
        if not session:
            logger.warning(f"Session ID '{request.session_id}' not found or invalid. Creating a new session.")
            session_id = session_manager.create_session()
        else:
            session_id = session.session_id

        logger.info(f"Using session ID: {session_id}")
        
        # Add user message to history
        session_manager.add_message(session_id, "user", request.message)
        
        # Get chat history and customer info before processing
        history_before_processing = session_manager.get_history(session_id) or []
        customer_info = session_manager.get_customer_info(session_id) or {}
        
        # Process message using AgentCoordinator with history and customer info
        result = await agent_coordinator.process_message(request.message, history_before_processing, customer_info)
        logger.info(f"Agent response: {result}")
        
        # Add bot response to history
        session_manager.add_message(session_id, "assistant", result["response"], metadata={"intent": result})
        
        # Get updated chat history for the response
        final_history = session_manager.get_history(session_id) or []
        
        # Create response data
        response_data = ChatResponseData(
            response=result["response"],
            session_id=session_id,
            intent={"intent": result.get("agent_used", "general"), "confidence": result.get("confidence", 1.0)},
            history=final_history,
            customer_info=customer_info
        )
        
        return ApiResponse(
            success=True,
            message="Message processed successfully",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session/{session_id}")
async def get_session_history(session_id: str):
    logger.info(f"Getting history for session: {session_id}")
    history = session_manager.get_history(session_id)
    if history is None:
        logger.warning(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {"history": history}

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    logger.info(f"Attempting to delete session: {session_id}")
    if session_manager.delete_session(session_id):
        return {"message": "Session deleted successfully"}
    logger.warning(f"Failed to delete session: {session_id}")
    raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

@app.get("/api/sessions")
async def list_sessions():
    """List all active sessions"""
    logger.info("Listing all active sessions")
    return {"sessions": list(session_manager.sessions.keys())}

@app.post("/api/customer/update")
async def update_customer_info(update: CustomerInfoUpdate):
    try:
        success = session_manager.update_customer_info(
            update.session_id,
            name=update.name,
            email=update.email
        )
        if success:
            return {"success": True, "message": "Customer information updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        logger.error(f"Error updating customer info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
