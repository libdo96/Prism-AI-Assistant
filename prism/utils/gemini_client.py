import os
import google.generativeai as genai
import io
import base64
import cv2
import numpy as np
import logging
from PIL import Image
import traceback
from dotenv import load_dotenv

from .web_search import WebSearchClient

class GeminiClient:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize Gemini
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables. Please check your .env file.")
        
        try:
            genai.configure(api_key=api_key)
            # Use gemini-1.5-flash which is multimodal
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.web_search = WebSearchClient()
            logging.info("Gemini model initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing Gemini model: {e}")
            logging.error(traceback.format_exc())
            raise
        
        # Initialize conversation history
        self.conversation_history = []
        self.max_history = 10  # Keep last 10 turns
        
        # Add system message to guide the model
        self.system_message = """You are Prism, an AI assistant with the following capabilities:
        1. Web Search: For factual queries, current events, or when you need to verify information
        2. Image Analysis: When the user shares an image or uses their camera
        3. General Conversation: For questions about your capabilities or general chat
        4. Also if user asks questions in hindi then always repons in hinglish language
        
        Always be concise and direct in your responses. If using web search, cite your sources.
        If analyzing an image, describe what you see and provide relevant insights."""
        
        self.conversation_history.append({"role": "system", "content": self.system_message})
        
        # For status updates
        self.status_update = None
    
    def set_status_callback(self, callback):
        """Set callback for UI status updates"""
        self.status_update = callback
    
    def _format_history(self):
        """Format conversation history for the prompt"""
        try:
            formatted = []
            for msg in self.conversation_history[-self.max_history:]:
                role = "Assistant" if msg["role"] == "assistant" else "User"
                formatted.append(f"{role}: {msg['content']}")
            return "\n".join(formatted)
        except Exception as e:
            logging.error(f"Error formatting history: {e}")
            logging.error(traceback.format_exc())
            return ""
    
    def _get_previous_user_query(self):
        """Get the most recent user query that is not a command"""
        # Filter out system messages and commands
        user_messages = [msg for msg in self.conversation_history 
                        if msg.get("role") == "user"]
        
        # Check from most recent to oldest
        if len(user_messages) >= 2:
            previous_query = user_messages[-2].get("content", "")
            # Exclude simple commands
            command_phrases = ["search for", "perform a web search", "web search", 
                             "search", "look up", "find information"]
            
            is_command = any(phrase in previous_query.lower() for phrase in command_phrases)
            if not is_command and len(previous_query.split()) >= 3:
                return previous_query
            
            # If most recent was command, try the one before
            if len(user_messages) >= 3:
                older_query = user_messages[-3].get("content", "")
                is_command = any(phrase in older_query.lower() for phrase in command_phrases)
                if not is_command:
                    return older_query
        
        return None
    
    def _prepare_image(self, image):
        """Prepare image for Gemini vision model"""
        try:
            logging.info("Starting image preparation...")
            
            if isinstance(image, np.ndarray):
                logging.info("Converting OpenCV image to PIL...")
                # Convert OpenCV image to PIL
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(image)
            elif isinstance(image, str):
                logging.info(f"Loading image from file: {image}")
                # Load from file path
                image = Image.open(image)
            
            # Verify image is valid
            if not image or image.size[0] == 0 or image.size[1] == 0:
                raise ValueError("Invalid image dimensions")
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                logging.info("Converting image to RGB mode...")
                image = image.convert('RGB')
            
            # Log image details
            logging.info(f"Image prepared successfully. Size: {image.size}, Mode: {image.mode}")
            return image
        except Exception as e:
            logging.error(f"Error preparing image: {e}")
            logging.error(traceback.format_exc())
            return None
    
    def _image_to_base64(self, image):
        """Convert PIL Image to base64 string"""
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            return img_str
        except Exception as e:
            logging.error(f"Error converting image to base64: {e}")
            logging.error(traceback.format_exc())
            return None
    
    def generate_response(self, query, image=None):
        """Generate a response using Gemini model, optionally with image analysis or web search"""
        try:
            # Add user message to history
            self.conversation_history.append({"role": "user", "content": query})
            
            # Prepare log message
            log_msg = f"Generating response for: '{query[:50]}...'" if len(query) > 50 else f"Generating response for: '{query}'"
            logging.info(log_msg)
            
            # Update UI status if callback is set
            if self.status_update:
                self.status_update("Thinking...")
            
            processed_image = None
            if image is not None:
                logging.info("Image provided, preparing for analysis")
                if self.status_update:
                    self.status_update("Analyzing image...")
                processed_image = self._prepare_image(image)
            
            # Decide if we need web search
            decision_prompt = f"""Based on the following conversation history and the current query, 
            determine if a web search is needed. Reply with only 'WEB_SEARCH' or 'NO_SEARCH'.

            Conversation history:
            {self._format_history()}
            
            Current query: {query}
            
            A web search is needed when:
            - The query asks for current events, news, or time-sensitive information
            - The query asks for factual information that might not be in your training data
            - The query explicitly asks to search for something
            
            Reply with only 'WEB_SEARCH' or 'NO_SEARCH'."""
            
            action_decision = "NO_SEARCH"
            
            try:
                decision_response = self.model.generate_content(decision_prompt)
                action_text = decision_response.text.strip().upper()
                
                # Check if the response contains the decision keyword
                if "WEB_SEARCH" in action_text:
                    action_decision = "WEB_SEARCH"
                    logging.info(f"Action decision: {action_decision}")
                else:
                    logging.info(f"Action decision: NO_SEARCH")
            except Exception as e:
                logging.error(f"Error in action decision: {e}")
                logging.error(traceback.format_exc())
            
            # Use web search if needed
            web_search_results = None
            if action_decision == "WEB_SEARCH":
                if self.status_update:
                    self.status_update("Searching the web...")
                
                # Check if we need context from previous query
                previous_query = self._get_previous_user_query()
                search_query = query
                
                # If current query is very short and seems like a follow-up
                if len(query.split()) <= 3 and previous_query:
                    combined_query = f"{previous_query} {query}"
                    logging.info(f"Using combined query for search: {combined_query}")
                    search_query = combined_query
                
                web_search_results = self.web_search.search(search_query)
                
                if web_search_results:
                    logging.info(f"Web search results found: {len(web_search_results)} items")
                else:
                    logging.info("No web search results found")
            
            # Prepare the final prompt
            if processed_image is not None:
                # Always handle image analysis if an image is provided
                logging.info("Generating response with image analysis")
                
                # Create a detailed prompt for image analysis
                image_prompt = f"""The user has provided an image along with this query: "{query}"
                
                Analyze the image thoroughly and respond to the query.
                
                If the query is about the image:
                1. Describe the relevant aspects of the image that relate to the query
                2. Answer the specific question or provide the information requested
                
                If the query doesn't explicitly mention the image:
                1. Assume the user wants information about what's in the image
                2. Describe the key elements of the image
                3. Relate your response to both the image content and the query
                
                Be detailed but concise in your analysis."""
                
                try:
                    # Try direct multimodal input
                    response = self.model.generate_content([image_prompt, processed_image])
                    answer = response.text
                except Exception as e:
                    logging.error(f"Error with direct multimodal input: {e}")
                    try:
                        # Try with parts format
                        response = self.model.generate_content({
                            "contents": [
                                {
                                    "role": "user",
                                    "parts": [
                                        {"text": image_prompt},
                                        {"inline_data": {
                                            "mime_type": "image/jpeg",
                                            "data": self._image_to_base64(processed_image)
                                        }}
                                    ]
                                }
                            ]
                        })
                        answer = response.text
                    except Exception as e2:
                        logging.error(f"Error with parts format: {e2}")
                        # Last resort: resize image and try again
                        try:
                            smaller_image = processed_image.resize((800, 600))
                            response = self.model.generate_content([image_prompt, smaller_image])
                            answer = response.text
                        except Exception as e3:
                            logging.error(f"All image analysis methods failed: {e3}")
                            answer = "I apologize, but I'm having trouble analyzing the image. Could you try again with a different image or describe what you're looking for?"
            
            elif web_search_results:
                # Web search with results
                search_prompt = f"""Based on the following web search results and conversation history, 
                answer the user's query: "{query}"

                Conversation history:
                {self._format_history()}
                
                Web search results:
                {web_search_results}
                
                Important guidelines:
                1. Use ONLY the information from the search results to answer
                2. If the search results don't contain relevant information, say so
                3. Cite sources using [Source: URL] format
                4. Be concise and factual
                5. Format your response in a readable way
                """
                
                response = self.model.generate_content(search_prompt)
                answer = response.text
            
            else:
                # Standard response without tools
                standard_prompt = f"""Based on the following conversation history, 
                answer the user's query: "{query}"

                Conversation history:
                {self._format_history()}
                
                Guidelines:
                1. Be helpful, accurate and concise
                2. If you don't know the answer, say so rather than making something up
                3. If it's a complex topic, break down your explanation into clear points
                4. If the query is in Hindi, respond in Hinglish (Hindi written in English)
                """
                
                response = self.model.generate_content(standard_prompt)
                answer = response.text
            
            # Add response to history
            self.conversation_history.append({"role": "assistant", "content": answer})
            
            # Keep history within limits
            if len(self.conversation_history) > self.max_history + 1:  # +1 for system message
                self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-(self.max_history):]
            
            # Update UI status if callback is set
            if self.status_update:
                self.status_update("Ready")
            
            return answer
            
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            logging.error(traceback.format_exc())
            if self.status_update:
                self.status_update("Error encountered, please try again")
            return f"I apologize, but I encountered an error: {str(e)}. Please try again." 