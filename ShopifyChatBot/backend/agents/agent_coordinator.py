from typing import Dict, Any, List, Optional
import logging
import traceback
from agents.guard_agent import GuardAgent
from agents.input_classifier_agent import InputClassifierAgent
from agents.recommendation_agent import RecommendationAgent
from agents.order_agent import OrderAgent
from agents.gpt_humanizer_agent import GPTHumanizerAgent
from agents.product_info_agent import ProductInfoAgent

logger = logging.getLogger(__name__)

class AgentCoordinator:
    """
    Coordinates different agents and manages the conversation flow.
    """
    
    def __init__(self):
        logger.info("Initializing AgentCoordinator")
        self.guard_agent = GuardAgent()
        self.classifier_agent = InputClassifierAgent()
        self.recommendation_agent = RecommendationAgent()
        self.order_agent = OrderAgent()
        self.humanizer_agent = GPTHumanizerAgent()
        self.product_info_agent = ProductInfoAgent()
        
    async def process_message(self, message: str, history: List[Dict] = None, customer_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process an incoming message and return a response.
        
        Args:
            message: The user's message
            history: List of previous messages in the conversation
            customer_info: Dictionary containing customer details (name, email, etc.)
            
        Returns:
            Dict containing the response and any additional metadata
        """
        logger.debug(f"Processing message: {message}")
        
        try:
            # Step 1: Check message safety
            safety_check = await self.guard_agent.check_message(message)
            if not safety_check["is_safe"]:
                humanized_response = await self.humanizer_agent.humanize_response({
                    "response": f"Message rejected: {safety_check['reason']}",
                    "agent_used": "guard_agent",
                    "history": history,
                    "customer_info": customer_info
                })
                return {
                    "response": humanized_response,
                    "confidence": safety_check["confidence"],
                    "agent_used": "guard_agent",
                    "customer_info": customer_info
                }
                
            # Step 2: Classify the input
            classification = await self.classifier_agent.classify_input(message)
            logger.info(f"Message classified as: {classification}")
            
            # Step 3: Route to appropriate agent based on intent
            if classification["intent"] == "order":
                try:
                    # Extract order number first
                    logger.debug("Attempting to extract order number")
                    order_number = self.order_agent.extract_order_number(message)
                    logger.info(f"Extracted order number: {order_number}")
                    
                    if not order_number:
                        humanized_response = await self.humanizer_agent.humanize_response({
                            "response": "I couldn't find an order number in your message. Please provide an order number.",
                            "agent_used": "order_agent",
                            "history": history,
                            "customer_info": customer_info
                        })
                        return {
                            "response": humanized_response,
                            "confidence": classification["confidence"],
                            "agent_used": "order_agent",
                            "customer_info": customer_info
                        }

                    # Fetch order details
                    logger.debug(f"Fetching details for order #{order_number}")
                    order_details = await self.order_agent.fetch_order_details(order_number)
                    logger.info(f"Order details fetched: {order_details}")

                    # Check for errors in the response
                    if "errors" in order_details:
                        error_message = order_details['errors'][0]['message']
                        logger.error(f"Shopify API error: {error_message}")
                        humanized_response = await self.humanizer_agent.humanize_response({
                            "response": f"Sorry, I encountered an error while fetching your order: {error_message}",
                            "agent_used": "order_agent",
                            "history": history,
                            "customer_info": customer_info
                        })
                        return {
                            "response": humanized_response,
                            "confidence": classification["confidence"],
                            "agent_used": "order_agent",
                            "error": error_message,
                            "customer_info": customer_info
                        }

                    # Check if we found any orders
                    orders = order_details.get("data", {}).get("orders", {}).get("edges", [])
                    if not orders:
                        logger.info(f"No order found with number #{order_number}")
                        humanized_response = await self.humanizer_agent.humanize_response({
                            "response": f"I couldn't find any order with number #{order_number}",
                            "agent_used": "order_agent",
                            "history": history,
                            "customer_info": customer_info
                        })
                        return {
                            "response": humanized_response,
                            "confidence": classification["confidence"],
                            "agent_used": "order_agent",
                            "customer_info": customer_info
                        }

                    # Format the order details
                    order = orders[0]["node"]
                    logger.debug(f"Processing order details: {order}")
                    
                    raw_agent_response = f"I'm happy to tell you about your order #{order_number}!\n\n"
                    
                    # Add status with more natural language
                    if "displayFulfillmentStatus" in order:
                        status = order['displayFulfillmentStatus'].lower()
                        if status == "fulfilled":
                            raw_agent_response += f"Great news! Your order has been fulfilled and is on its way. "
                        elif status == "unfulfilled":
                            raw_agent_response += f"Your order is currently being processed. "
                        else:
                            raw_agent_response += f"Your order status is: {order['displayFulfillmentStatus']}. "
                    
                    # Add total with more context
                    total = order.get("totalPriceSet", {}).get("shopMoney", {})
                    if total:
                        raw_agent_response += f"You paid {total.get('amount', 'Unknown')} {total.get('currencyCode', '')} for your purchase.\n\n"
                    
                    # Add line items with more engaging descriptions
                    line_items = order.get("lineItems", {}).get("edges", [])
                    if line_items:
                        raw_agent_response += "Here's what you ordered:\n"
                        for item in line_items:
                            node = item.get("node", {})
                            title = node.get('title', 'Unknown')
                            quantity = node.get('quantity', 'Unknown')
                            raw_agent_response += f"• {title} (Quantity: {quantity})\n"
                    
                    # Add shipping info if available
                    if "shippingAddress" in order:
                        shipping = order["shippingAddress"]
                        if shipping:
                            raw_agent_response += f"\nYour order will be delivered to:\n{shipping.get('address1', '')}\n"
                            if shipping.get('city'):
                                raw_agent_response += f"{shipping['city']}, {shipping.get('province', '')} {shipping.get('zip', '')}\n"
                            if shipping.get('country'):
                                raw_agent_response += f"{shipping['country']}\n"

                    # Add a personalized note about the order
                    if line_items:
                        first_item = line_items[0]["node"].get("title", "")
                        raw_agent_response += f"\nI think you made a great choice with the {first_item}! "
                        raw_agent_response += "It's a popular item that our customers love. "
                        raw_agent_response += "Is there anything specific about your order you'd like to know more about?"

                    logger.info(f"Successfully formatted order response for order #{order_number}")
                    humanized_response = await self.humanizer_agent.humanize_response({
                        "response": raw_agent_response,
                        "agent_used": "order_agent",
                        "order_details": order,
                        "history": history,
                        "customer_info": customer_info
                    })
                    return {
                        "response": humanized_response,
                        "confidence": classification["confidence"],
                        "agent_used": "order_agent",
                        "order_details": order,
                        "customer_info": customer_info
                    }

                except Exception as e:
                    error_details = traceback.format_exc()
                    logger.error(f"Error processing order request: {str(e)}\n{error_details}")
                    humanized_response = await self.humanizer_agent.humanize_response({
                        "response": f"I apologize, but I encountered an error while processing your order request: {str(e)}",
                        "agent_used": "order_agent",
                        "history": history,
                        "customer_info": customer_info
                    })
                    return {
                        "response": humanized_response,
                        "confidence": 0.0,
                        "agent_used": "order_agent",
                        "error": str(e),
                        "error_details": error_details,
                        "customer_info": customer_info
                    }

            elif classification["intent"] == "recommendation":
                result = await self.recommendation_agent.get_recommendations(message)

                # Check if recommendations were successfully fetched
                if "recommendations" in result and result["recommendations"]:
                    # Format the recommendations into a string for the humanizer
                    recommendations_list_str = "\n".join([
                        f"- {item.get('name', 'Unknown Product')} (Price: {item.get('price', 'N/A')} {item.get('currency', '')})"
                        for item in result["recommendations"]
                    ])
                    raw_humanizer_input = f"Here are some products I recommend:\n{recommendations_list_str}"
                else:
                    raw_humanizer_input = result.get("reason", "I couldn't find any specific recommendations at the moment. Please try again later.")

                humanized_response = await self.humanizer_agent.humanize_response({
                    "response": raw_humanizer_input,
                    "agent_used": "recommendation_agent",
                    "recommendations": result["recommendations"],
                    "history": history,
                    "customer_info": customer_info
                })
                return {
                    "response": humanized_response,
                    "confidence": classification["confidence"],
                    "agent_used": "recommendation_agent",
                    "recommendations": result["recommendations"],
                    "customer_info": customer_info
                }
            elif classification["intent"] in ["product_price", "product_stock", "return_policy", "product_info"]:
                # Process product information requests
                product_info_result = await self.product_info_agent.process_product_info_request(message, classification["intent"])
                humanized_response = await self.humanizer_agent.humanize_response({
                    "response": product_info_result["response"],
                    "agent_used": product_info_result["agent_used"],
                    "product_details": product_info_result.get("product_details"),
                    "history": history,
                    "customer_info": customer_info
                })
                return {
                    "response": humanized_response,
                    "confidence": product_info_result["confidence"],
                    "agent_used": product_info_result["agent_used"],
                    "product_details": product_info_result.get("product_details"),
                    "customer_info": customer_info
                }
            else:
                # Default response for general queries
                raw_agent_response = f"I'm your shopping assistant. You said: {message}"
                humanized_response = await self.humanizer_agent.humanize_response({
                    "response": raw_agent_response,
                    "agent_used": "general",
                    "history": history,
                    "customer_info": customer_info
                })
                return {
                    "response": humanized_response,
                    "confidence": classification["confidence"],
                    "agent_used": "general",
                    "customer_info": customer_info
                }
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Unhandled error in AgentCoordinator.process_message: {str(e)}\n{error_details}")
            return {
                "response": "I apologize, but I encountered an unexpected error while processing your request. Please try again later.",
                "confidence": 0.0,
                "agent_used": "error_handler",
                "error": str(e),
                "error_details": error_details,
                "customer_info": customer_info
            }