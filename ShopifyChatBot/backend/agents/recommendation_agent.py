from typing import Dict, Any, List, Optional
import logging
import os
from dotenv import load_dotenv
import aiohttp
import json
import openai

logger = logging.getLogger(__name__)

# Load and check environment variables
load_dotenv()
logger.info("Environment variables loaded for RecommendationAgent")

class RecommendationAgent:
    """
    Provides product recommendations based on user input.
    """
    
    def __init__(self):
        logger.info("Initializing RecommendationAgent")
        self.shopify_access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.shopify_store_url = os.getenv('SHOPIFY_STORE_URL')
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.shopify_access_token or not self.shopify_store_url:
            raise ValueError("Missing required Shopify credentials for RecommendationAgent")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set for RecommendationAgent.")

        self.graphql_url = f"https://{self.shopify_store_url}/admin/api/2024-01/graphql.json"
        self.headers = {
            'X-Shopify-Access-Token': self.shopify_access_token,
            'Content-Type': 'application/json',
        }
        self.openai_client = openai.AsyncOpenAI(api_key=self.openai_api_key)

    async def _extract_keywords_with_gpt(self, message: str) -> Optional[str]:
        """
        Uses GPT to extract relevant product keywords or categories from the user's message.
        """
        prompt = f"""Extract the main product categories or keywords from the following user query.
        If no clear product is mentioned, return 'general'. Return only the keyword(s) or 'general', nothing else.

        Examples:
        User: 'Can you recommend some Levi's Jeans?'
        Output: 'Levi's Jeans'

        User: 'Show me some cool items'
        Output: 'general'

        User: 'I'm looking for a new t-shirt'
        Output: 't-shirt'

        User: '{message}'
        Output:"""

        try:
            response = await self.openai_client.completions.create(
                model="gpt-3.5-turbo-instruct", # Using instruct model for simplicity
                prompt=prompt,
                max_tokens=20,
                n=1,
                stop=None,
                temperature=0.0 # Keep temperature low for precise extraction
            )
            keywords = response.choices[0].text.strip()
            logger.debug(f"GPT extracted keywords: {keywords}")
            if keywords.lower() == 'general' or not keywords:
                return None # Return None to fetch general products if no specific keyword
            return keywords
        except Exception as e:
            logger.error(f"Error extracting keywords with GPT: {e}", exc_info=True)
            return None # Fallback to no specific query

    async def fetch_products(self, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch product details from Shopify using GraphQL.
        If a query string is provided, it will filter products.
        """
        graphql_query = """
        query getProducts($query: String) {
            products(first: 5, query: $query) {
                edges {
                    node {
                        id
                        title
                        description
                        onlineStoreUrl
                        priceRange {
                            minVariantPrice {
                                amount
                                currencyCode
                            }
                        }
                        images(first: 1) {
                            edges {
                                node {
                                    src
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {}
        if query:
            variables["query"] = query

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": graphql_query, "variables": variables}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Raw Shopify product response: {json.dumps(data, indent=2)}")
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"Error fetching products: {error_text}")
                    return {"error": f"Failed to fetch products: {error_text}"}

    async def get_recommendations(self, message: str) -> Dict[str, Any]:
        """
        Generate product recommendations based on the message by fetching from Shopify.
        """
        logger.debug(f"Generating recommendations for: {message}")
        
        # Use GPT to extract relevant keywords from the message
        search_query = await self._extract_keywords_with_gpt(message)
        logger.info(f"Extracted search query for Shopify: {search_query}")

        shopify_response = await self.fetch_products(query=search_query)
        
        if "errors" in shopify_response:
            error_message = shopify_response['errors'][0]['message'] if shopify_response['errors'] else "Unknown Shopify API error."
            logger.error(f"Shopify API error in recommendations: {error_message}")
            return {
                "recommendations": [],
                "confidence": 0.0,
                "reason": f"Failed to fetch recommendations from Shopify: {error_message}",
                "error": error_message
            }

        products = shopify_response.get("data", {}).get("products", {}).get("edges", [])
        
        recommendations = []
        for item in products:
            node = item.get("node", {})
            if node:
                recommendations.append({
                    "id": node.get("id"),
                    "name": node.get("title"),
                    "price": node.get("priceRange", {}).get("minVariantPrice", {}).get("amount", "N/A"),
                    "currency": node.get("priceRange", {}).get("minVariantPrice", {}).get("currencyCode", ""),
                    "description": node.get("description"),
                    "url": node.get("onlineStoreUrl"),
                    "image": node.get("images", {}).get("edges", [{}])[0].get("node", {}).get("src")
                })
        
        if not recommendations:
            logger.info("No recommendations found from Shopify.")
            return {
                "recommendations": [],
                "confidence": 0.5,
                "reason": "No products found from Shopify."
            }

        return {
            "recommendations": recommendations,
            "confidence": 0.9,
            "reason": "Fetched from Shopify API"
        } 