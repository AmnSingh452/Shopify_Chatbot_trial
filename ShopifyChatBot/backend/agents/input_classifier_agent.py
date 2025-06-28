from typing import Dict, Any
import logging
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class InputClassifierAgent:
    """
    Classifies the intent of the user's input using an LLM.
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.client = AsyncOpenAI(api_key=self.api_key)
        logger.info("InputClassifierAgent initialized.")

    async def classify_input(self, user_input: str) -> Dict[str, Any]:
        """
        Classifies the intent of the user's input.
        
        Args:
            user_input: The user's raw message.
            
        Returns:
            A dictionary containing the classified intent and confidence score.
        """
        logger.debug(f"Classifying input: {user_input}")
        
        system_message = {"role": "system", "content": "You are an expert in classifying user intent for an e-commerce chatbot. Classify the user's intent into one of the following categories: 'order', 'recommendation', 'product_price', 'product_stock', 'return_policy', or 'general'. Provide a confidence score (0.0 to 1.0) and a brief explanation."
        }
        
        examples = [
            # Order intent examples
            {"role": "user", "content": "Where is my order #1234?"},
            {"role": "assistant", "content": "{\"intent\": \"order\", \"confidence\": 0.9, \"explanation\": \"User is asking about an order status.\"}"},
            {"role": "user", "content": "Can you update order 5678?"},
            {"role": "assistant", "content": "{\"intent\": \"order\", \"confidence\": 0.85, \"explanation\": \"User wants to modify an order.\"}"},
            {"role": "user", "content": "I need details for order 9012."},
            {"role": "assistant", "content": "{\"intent\": \"order\", \"confidence\": 0.92, \"explanation\": \"User is requesting order details.\"}"},

            # Recommendation intent examples
            {"role": "user", "content": "Recommend some shoes"},
            {"role": "assistant", "content": "{\"intent\": \"recommendation\", \"confidence\": 0.9, \"explanation\": \"User is asking for product recommendations.\"}"},
            {"role": "user", "content": "What should I buy?"},
            {"role": "assistant", "content": "{\"intent\": \"recommendation\", \"confidence\": 0.75, \"explanation\": \"User is asking for general product suggestions.\"}"},
            {"role": "user", "content": "Do you have any cool gadgets?"},
            {"role": "assistant", "content": "{\"intent\": \"recommendation\", \"confidence\": 0.88, \"explanation\": \"User is looking for specific product types to be recommended.\"}"},
            
            # Product Price intent examples
            {"role": "user", "content": "How much is the Levi's 501 jeans?"},
            {"role": "assistant", "content": "{\"intent\": \"product_price\", \"confidence\": 0.95, \"explanation\": \"User is inquiring about the price of a specific product.\"}"},
            {"role": "user", "content": "What's the cost of the graphic t-shirt?"},
            {"role": "assistant", "content": "{\"intent\": \"product_price\", \"confidence\": 0.9, \"explanation\": \"User wants to know the price.\"}"},

            # Product Stock intent examples
            {"role": "user", "content": "Is the iPhone 15 in stock?"},
            {"role": "assistant", "content": "{\"intent\": \"product_stock\", \"confidence\": 0.95, \"explanation\": \"User is inquiring about product availability.\"}"},
            {"role": "user", "content": "Do you have size M in the black dress?"},
            {"role": "assistant", "content": "{\"intent\": \"product_stock\", \"confidence\": 0.9, \"explanation\": \"User is asking about stock for a specific variant.\"}"},

            # Return Policy intent examples
            {"role": "user", "content": "What's your return policy?"},
            {"role": "assistant", "content": "{\"intent\": \"return_policy\", \"confidence\": 0.98, \"explanation\": \"User is asking about the store's return policy.\"}"},
            {"role": "user", "content": "Can I return this item?"},
            {"role": "assistant", "content": "{\"intent\": \"return_policy\", \"confidence\": 0.92, \"explanation\": \"User is asking about eligibility for return.\"}"},

            # General intent examples
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "{\"intent\": \"general\", \"confidence\": 0.8, \"explanation\": \"A generic greeting.\"}"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "{\"intent\": \"general\", \"confidence\": 0.7, \"explanation\": \"A general conversational query.\"}"}
        ]
        
        messages = [system_message] + examples + [{"role": "user", "content": user_input}]
        
        try:
            chat_completion = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.0, # Keep temperature low for precise classification
                max_tokens=100
            )
            
            response_content = chat_completion.choices[0].message.content
            logger.info(f"Raw classification response: {response_content}")
            
            # Attempt to parse the JSON response
            try:
                classification_result = json.loads(response_content)
                # Validate the structure
                if "intent" not in classification_result or "confidence" not in classification_result:
                    raise ValueError("Invalid classification format from LLM")
                return classification_result
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON from classifier: {response_content}")
                # Fallback to a default general intent if parsing fails
                return {"intent": "general", "confidence": 0.5, "explanation": "Failed to parse LLM response."}

        except Exception as e:
            logger.error(f"Error classifying input with OpenAI: {e}", exc_info=True)
            # Fallback to general intent in case of API error
            return {"intent": "general", "confidence": 0.0, "explanation": f"API error: {str(e)}"}