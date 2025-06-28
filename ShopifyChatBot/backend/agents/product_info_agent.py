import logging
import os
from dotenv import load_dotenv
import aiohttp
import json
from typing import Dict, Any, Optional
import re
import openai

logger = logging.getLogger(__name__)

load_dotenv()
logger.info("Environment variables loaded for ProductInfoAgent")

class ProductInfoAgent:
    """
    Handles queries related to product information like stock, price, and return policy.
    """
    def __init__(self):
        logger.info("Initializing ProductInfoAgent")
        self.shopify_access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.shopify_store_url = os.getenv('SHOPIFY_STORE_URL')
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        if not self.shopify_access_token or not self.shopify_store_url:
            raise ValueError("Missing required Shopify credentials for ProductInfoAgent")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set for ProductInfoAgent.")

        self.graphql_url = f"https://{self.shopify_store_url}/admin/api/2024-01/graphql.json"
        self.headers = {
            'X-Shopify-Access-Token': self.shopify_access_token,
            'Content-Type': 'application/json',
        }
        self.openai_client = openai.AsyncOpenAI(api_key=self.openai_api_key)

    async def _extract_product_name_with_gpt(self, message: str) -> Optional[str]:
        """
        Uses GPT to extract the main product name from the user's message.
        """
        prompt = f"""Extract ONLY the exact product name from the following user query. Respond with 'NONE' if no clear product name is mentioned.

        Examples:
        User: 'How much is the Levi's 501 jeans?'
        Output: Levi's 501 jeans

        User: 'Is the iPhone 15 in stock?'
        Output: iPhone 15

        User: 'Tell me about the Short-sleeve tshirt.'
        Output: Short-sleeve tshirt

        User: 'What is your return policy?'
        Output: NONE

        User: '{message}'
        Output:"""

        try:
            response = await self.openai_client.completions.create(
                model="gpt-3.5-turbo-instruct",
                prompt=prompt,
                max_tokens=20,
                n=1,
                stop=['\n\n'],
                temperature=0.0
            )
            extracted_name = response.choices[0].text.strip()
            logger.debug(f"GPT extracted product name: {extracted_name}")
            if extracted_name.lower() == 'none' or not extracted_name:
                return None
            return extracted_name
        except Exception as e:
            logger.error(f"Error extracting product name with GPT: {e}", exc_info=True)
            return None

    async def _extract_product_name(self, message: str) -> Optional[str]:
        """
        Extracts a potential product name from the user's message using GPT as primary, with a basic fallback.
        """
        gpt_extracted_name = await self._extract_product_name_with_gpt(message)
        if gpt_extracted_name:
            return gpt_extracted_name
        
        # Fallback to very basic extraction if GPT fails or doesn't find a product
        product_keywords = []
        words = message.split()
        for i, word in enumerate(words):
            if word.istitle() and len(word) > 2:
                name_candidate = word
                for j in range(i + 1, min(i + 3, len(words))):
                    if words[j].istitle() or words[j].islower() and len(words[j]) > 2:
                        name_candidate += f" {words[j]}"
                    else:
                        break
                product_keywords.append(name_candidate)
        return product_keywords[0] if product_keywords else None

    async def fetch_product_details(self, product_query: str) -> Dict[str, Any]:
        """
        Fetches detailed product information from Shopify based on a query.
        """
        query = """
        query getProductDetails($query: String!) {
            products(first: 1, query: $query) {
                edges {
                    node {
                        id
                        title
                        totalInventory
                        priceRange {
                            minVariantPrice {
                                amount
                                currencyCode
                            }
                        }
                        description
                        onlineStoreUrl
                    }
                }
            }
        }
        """
        variables = {
            "query": product_query
        }

        logger.debug(f"Shopify product details query variables: {variables}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": query, "variables": variables}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Raw Shopify product details response: {json.dumps(data, indent=2)}")
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"Error fetching product details: {error_text}")
                    return {"error": f"Failed to fetch product details: {error_text}"}

    async def process_product_info_request(self, message: str, intent: str) -> Dict[str, Any]:
        """
        Processes queries related to product stock, price, or return policy.
        """
        product_name = await self._extract_product_name(message)
        logger.info(f"Product name extracted for ProductInfoAgent: {product_name}")
        if not product_name:
            return {
                "response": "I couldn't identify a specific product in your query. Could you please specify the product name?",
                "confidence": 0.5,
                "agent_used": "product_info_agent"
            }

        product_details_response = await self.fetch_product_details(product_name)

        if "errors" in product_details_response:
            error_message = product_details_response['errors'][0]['message'] if product_details_response['errors'] else "Unknown Shopify API error."
            logger.error(f"Shopify API error in ProductInfoAgent: {error_message}")
            return {
                "response": f"Sorry, I encountered an error while fetching product details: {error_message}",
                "confidence": 0.0,
                "agent_used": "product_info_agent",
                "error": error_message
            }

        products = product_details_response.get("data", {}).get("products", {}).get("edges", [])
        if not products:
            return {
                "response": f"I couldn't find any product matching '{product_name}'. Please double-check the name.",
                "confidence": 0.6,
                "agent_used": "product_info_agent"
            }

        product = products[0]["node"]
        response_message = ""

        if intent == "product_price":
            price = product.get("priceRange", {}).get("minVariantPrice", {})
            amount_str = price.get("amount", "N/A")
            currency = price.get("currencyCode", "")
            
            try:
                amount = float(amount_str)
                # Assuming 2 decimal places for common currencies
                formatted_amount = f"{amount/100:.2f}" if amount_str != "N/A" else "N/A"
            except ValueError:
                formatted_amount = "N/A"

            product_title = product.get('title', 'this product').strip().replace('"', '') # Remove potential quotes
            response_message = f"The price of {product_title} is {formatted_amount} {currency}."
        elif intent == "product_stock":
            inventory = product.get("totalInventory", "N/A")
            product_title = product.get('title', 'this product').strip().replace('"', '') # Remove potential quotes
            response_message = f"There are {inventory} units of {product_title} currently in stock."
        elif intent == "return_policy":
            # Shopify API does not typically expose return policy per product.
            # This would usually be a static link or general statement from your store.
            response_message = f"Our return policy generally allows returns within 30 days of purchase for most items. For detailed information, please visit our Returns & Exchanges page on our website or contact customer support."
        else:
            # Default info if intent is general product_info
            price = product.get("priceRange", {}).get("minVariantPrice", {})
            amount_str = price.get("amount", "N/A")
            currency = price.get("currencyCode", "")
            inventory = product.get("totalInventory", "N/A")

            try:
                amount = float(amount_str)
                formatted_amount = f"{amount/100:.2f}" if amount_str != "N/A" else "N/A"
            except ValueError:
                formatted_amount = "N/A"

            product_title = product.get('title', 'this product').strip().replace('"', '') # Remove potential quotes
            response_message = (
                f"{product_title} is priced at {formatted_amount} {currency} and we currently have {inventory} units in stock. "
                f"For our return policy, please refer to the Returns & Exchanges section on our website."
            )
            
        return {
            "response": response_message,
            "confidence": 0.9,
            "agent_used": "product_info_agent",
            "product_details": product
        } 