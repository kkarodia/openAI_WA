import os
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv
from apiflask import APIFlask, Schema, abort
from apiflask.fields import String, Dict as DictField
from apiflask.validators import Length
from flask import jsonify, request

# API Configuration
API_TITLE = 'FNB API for Watson Assistant'
API_VERSION = '1.0.1'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Schema for Watson Assistant webhook format
class WatsonRequestSchema(Schema):
    text = String(required=True, validate=Length(min=1, max=2048))
    context = DictField(required=False)  # Watson context variables

class WatsonResponseSchema(Schema):
    response_type = String(default="text")
    text = String(required=True)
    context = DictField(required=False)

# Initialize Flask app
app = APIFlask(__name__, title=API_TITLE, version=API_VERSION)

# Configure OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Error handling
@app.errorhandler(Exception)
def handle_error(error: Exception) -> tuple[Dict[str, Any], int]:
    """Global error handler that maintains Watson Assistant webhook format"""
    logger.error(f"Error occurred: {str(error)}", exc_info=True)
    
    # Return error in Watson Assistant format
    return {
        'response_type': 'text',
        'text': "I apologize, but I'm having trouble processing your request right now. Please try again later.",
        'context': {
            'error': str(error),
            'status_code': getattr(error, 'status_code', 500)
        }
    }, 200  # Always return 200 for Watson Assistant webhooks

# Routes
@app.get('/')
def health_check() -> Dict[str, str]:
    """Health check endpoint for Cloud Engine"""
    return {'status': 'healthy', 'message': 'FNB API server is running'}

@app.post('/chat')
@app.input(WatsonRequestSchema)
@app.output(WatsonResponseSchema)
def chat_with_gpt(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chat endpoint that interfaces with GPT-3.5-turbo and returns responses in 
    Watson Assistant webhook format
    
    Args:
        json_data: Dictionary containing the text and context from Watson Assistant
        
    Returns:
        Dictionary formatted for Watson Assistant webhook response
    """
    try:
        # Log incoming request
        logger.info(f"Received request from Watson Assistant: {json_data.get('text', '')[:100]}...")
        
        # Extract conversation context if available
        context = json_data.get('context', {})
        
        response = client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": json_data['text']
            }],
            model="gpt-3.5-turbo",
            max_tokens=1024,  # Adjust based on your needs
            temperature=0.7
        )
        
        gpt_response = response.choices[0].message.content
        logger.info(f"GPT response generated: {gpt_response[:100]}...")
        
        # Return in Watson Assistant webhook format
        return {
            'response_type': 'text',
            'text': gpt_response,
            'context': {
                **context,  # Preserve existing context
                'last_gpt_response': gpt_response
            }
        }
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        # Return error in Watson Assistant format
        return {
            'response_type': 'text',
            'text': "I apologize, but I'm having trouble understanding right now. Please try again.",
            'context': {
                **context,  # Preserve existing context
                'error': str(e)
            }
        }

# Server configuration
def create_app() -> APIFlask:
    """Factory function to create the Flask app with configurations"""
    
    # Configure servers for OpenAPI spec
    app.config['SERVERS'] = [
        {
            'description': 'Code Engine deployment',
            'url': 'https://{appname}.{projectid}.{region}.codeengine.appdomain.cloud',
            'variables': {
                "appname": {
                    "default": "fnb-bot-backend",
                    "description": "application name"
                },
                "projectid": {
                    "default": "projectid",
                    "description": "the Code Engine project ID"
                },
                "region": {
                    "default": "us-south",
                    "description": "the deployment region"
                }
            }
        }
    ]
    
    return app

if __name__ == "__main__":
    port = int(os.getenv('PORT', '8080'))  # Cloud Engine often uses 8080
    app = create_app()
    app.run(host='0.0.0.0', port=port)