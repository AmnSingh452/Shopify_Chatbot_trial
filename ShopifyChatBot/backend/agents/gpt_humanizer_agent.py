import openai
import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class GPTHumanizerAgent:
    """
    Refines agent responses into more human-like, conversational language using GPT.
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.client = openai.AsyncOpenAI(api_key=self.api_key)
        logger.info("GPTHumanizerAgent initialized with AsyncOpenAI client.")

    async def humanize_response(self, agent_response: Dict[str, Any]) -> str:
        """
        Takes a structured agent response and converts it into a natural language response.
        
        Args:
            agent_response: A dictionary containing the agent's response and possibly other metadata.
                            Expected to have a 'response' key with the main content.
        
        Returns:
            A humanized string response.
        """
        raw_response = agent_response.get("response", "")
        agent_name = agent_response.get("agent_used", "unknown agent")
        history = agent_response.get("history", [])
        customer_info = agent_response.get("customer_info", {})

        # Ensure customer_info is a dictionary to prevent AttributeError
        if customer_info is None:
            customer_info = {}

        if not raw_response:
            return "I'm sorry, I couldn't generate a specific response for that. Can you please rephrase?"

        # Format conversation history for context
        history_context = ""
        if history:
            history_context = "\nPrevious conversation:\n"
            for msg in history[-3:]:  # Include last 3 messages for context
                role = "User" if msg["role"] == "user" else "Assistant"
                history_context += f"{role}: {msg['content']}\n"

        customer_name = customer_info.get("name")
        
        # Craft a persona-driven prompt
        if customer_name:
            greeting = f"Hi {customer_name}! "
        else:
            # For the very first message before a name is given
            greeting = "Hi there! I'm your friendly shopping assistant. To personalize our chat, what's your name? "
            # If the raw response is just a generic greeting, we can use our more specific one.
            if "Hi there" in raw_response:
                 return greeting

        prompt = f"""
        You are "Echo," an upbeat and very friendly shopping assistant. Your personality is enthusiastic, helpful, and a little bit fun. You are not a generic AI.
        Your goal is to rephrase the following 'raw agent response' into a short, casual, and personal message.

        **Rules:**
        - ALWAYS be concise. Keep responses to 1-2 sentences.
        - If you have the user's name ({customer_name}), use it.
        - Never sound like a generic AI or chatbot. Be natural.
        - If the agent's response is a simple greeting, make it a warm and welcoming one.

        **Conversation Context:**
        {history_context}

        **Raw Agent Response (from a backend system):**
        "{raw_response}"

        **Your Friendly Reply:**
        """
        
        # If there's no real history and no customer name, we force the introduction.
        if not history and not customer_name:
             return "Hi there! I'm Echo, your friendly shopping assistant. To help me personalize our chat, what should I call you?"

        logger.debug(f"Prompt sent to OpenAI: {prompt}")

        try:
            chat_completion = await self.client.completions.create(
                model="gpt-3.5-turbo-instruct",
                prompt=prompt.strip(), # Use strip() to remove leading/trailing whitespace
                max_tokens=150, # Reduced max_tokens for shorter responses
                n=1,
                stop=None,
                temperature=0.75, # Slightly adjusted for more creative but still focused responses
            )
            humanized_text = chat_completion.choices[0].text.strip()
            logger.info(f"Humanized response from {agent_name}: {humanized_text}")
            return humanized_text
        except Exception as e:
            logger.error(f"Error humanizing response: {e}", exc_info=True)
            # Fallback to the raw response if humanization fails
            return raw_response 