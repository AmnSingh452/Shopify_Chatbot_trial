from typing import Any, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None

def success_response(data: Any = None, message: str = "Operation successful") -> dict:
    """
    Create a standardized success response.
    
    Args:
        data: The data to be included in the response
        message: A success message
        
    Returns:
        dict: A standardized success response
    """
    response = APIResponse(
        success=True,
        message=message,
        data=data
    )
    logger.debug(f"Created success response: {response.dict()}")
    return response.dict()

def error_response(message: str, error: Optional[str] = None) -> dict:
    """
    Create a standardized error response.
    
    Args:
        message: A user-friendly error message
        error: Optional technical error details
        
    Returns:
        dict: A standardized error response
    """
    response = APIResponse(
        success=False,
        message=message,
        error=error
    )
    logger.debug(f"Created error response: {response.dict()}")
    return response.dict() 