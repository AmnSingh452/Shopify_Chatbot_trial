import asyncio
import logging
import os
from dotenv import load_dotenv
from agents.product_info_agent import ProductInfoAgent

# Configure logging to show DEBUG level messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Ensure environment variables are loaded
load_dotenv()

async def debug_product_info_agent():
    logger.info("Starting ProductInfoAgent debug script...")

    # Ensure necessary environment variables are set for testing
    if not os.getenv('SHOPIFY_ACCESS_TOKEN') or not os.getenv('SHOPIFY_STORE_URL'):
        logger.error("SHOPIFY_ACCESS_TOKEN and SHOPIFY_STORE_URL must be set in your .env file.")
        return
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY must be set in your .env file for product name extraction.")
        return

    agent = ProductInfoAgent()

    test_cases = [
        {"message": "What is the price of Coastal Plaid Shirt", "intent": "product_price"},
        {"message": "Is the Short-sleeve tshirt in stock?", "intent": "product_stock"},
        {"message": "Tell me about the Blue Jeans.", "intent": "product_info"},
        {"message": "What is your return policy?", "intent": "return_policy"},
        {"message": "Price of Non-existent Product?", "intent": "product_price"},
        {"message": "Check stock for Imaginary Item.", "intent": "product_stock"},
        {"message": "I'm looking for some pants.", "intent": "recommendation"} # Should be classified by ClassifierAgent, but useful to see general flow
    ]

    for i, test_case in enumerate(test_cases):
        print(f"\n--- Test Case {i+1} ---")
        print(f"Message: {test_case['message']}")
        print(f"Expected Intent: {test_case['intent']}")
        
        # Call the process_product_info_request directly
        # Note: If the classifier doesn't route it here, the intent needs to be explicitly passed.
        # For direct debugging of ProductInfoAgent, we pass the specified intent.
        response = await agent.process_product_info_request(test_case['message'], test_case['intent'])
        print(f"Agent Response: {response}")

if __name__ == "__main__":
    asyncio.run(debug_product_info_agent()) 