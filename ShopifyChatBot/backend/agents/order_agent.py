import asyncio
import logging
import json
import sys
import os
from dotenv import load_dotenv
import aiohttp
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load and check environment variables
load_dotenv()
logger.info("Environment variables loaded")
logger.info(f"SHOPIFY_ACCESS_TOKEN exists: {'Yes' if os.getenv('SHOPIFY_ACCESS_TOKEN') else 'No'}")
logger.info(f"SHOPIFY_STORE_URL exists: {'Yes' if os.getenv('SHOPIFY_STORE_URL') else 'No'}")
logger.info(f"OPENAI_API_KEY exists: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")

class OrderAgent:
    """
    Handles order-related queries and processing.
    """
    
    def __init__(self):
        self.shopify_access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.shopify_store_url = os.getenv('SHOPIFY_STORE_URL')
        
        if not self.shopify_access_token or not self.shopify_store_url:
            raise ValueError("Missing required Shopify credentials")
        
        self.graphql_url = f"https://{self.shopify_store_url}/admin/api/2024-01/graphql.json"
        self.headers = {
            'X-Shopify-Access-Token': self.shopify_access_token,
            'Content-Type': 'application/json',
        }

    def extract_order_number(self, message: str) -> Optional[str]:
        """Extract order number from user message."""
        # Simple regex pattern for order numbers
        import re
        pattern = r'#?(\d{4,})'
        match = re.search(pattern, message)
        return match.group(1) if match else None

    async def fetch_order_details(self, order_number: str) -> Dict[str, Any]:
        """Fetch order details from Shopify using GraphQL."""
        query = """
        query getOrder($query: String!) {
            orders(first: 1, query: $query) {
                edges {
                    node {
                        id
                        name
                        createdAt
                        displayFulfillmentStatus
                        displayFinancialStatus
                        totalPriceSet {
                            shopMoney {
                                amount
                                currencyCode
                            }
                        }
                        lineItems(first: 10) {
                            edges {
                                node {
                                    title
                                    quantity
                                }
                            }
                        }
                        customer {
                            firstName
                            lastName
                            email
                        }
                        shippingAddress {
                            address1
                            city
                            province
                            zip
                            country
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "query": f"name:\"#{order_number}\""
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": query, "variables": variables}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Raw Shopify response: {json.dumps(data, indent=2)}")
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"Error fetching order: {error_text}")
                    return {"error": f"Failed to fetch order: {error_text}"}

    async def process_order_request(self, message: str) -> Dict[str, Any]:
        """
        Process an order-related request.
        
        Args:
            message: The user's message
            
        Returns:
            Dict containing order processing results
        """
        try:
            order_number = self.extract_order_number(message)
            if not order_number:
                return {
                    "success": False,
                    "message": "Could not find an order number in your message. Please provide an order number."
                }
            
            order_details = await self.fetch_order_details(order_number)
            
            # Check if we got any errors in the response
            if "errors" in order_details:
                return {
                    "success": False,
                    "message": f"Error fetching order details: {json.dumps(order_details['errors'])}"
                }
            
            # Check if we found any orders
            orders = order_details.get("data", {}).get("orders", {}).get("edges", [])
            if not orders:
                return {
                    "success": False,
                    "message": f"No order found with number {order_number}"
                }
            
            return {
                "success": True,
                "order_number": order_number,
                "details": orders[0]["node"]
            }
        except Exception as e:
            logger.error(f"Error processing order request: {str(e)}")
            return {
                "success": False,
                "message": f"Error processing your request: {str(e)}"
            } 