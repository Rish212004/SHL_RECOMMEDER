"""
FastAPI Application
===================
YEH FILE KYA KARTI HAI:
- FastAPI server setup karta hai
- /health aur /chat endpoints expose karta hai
- Request/response validation karta hai Pydantic se
- Error handling karta hai

KYUN FASTAPI:
- Fast, modern, async support
- Built-in validation Pydantic ke saath
- Auto-generated docs (/docs pe jaao)
- Assignment mein specify kiya hai FastAPI

API DESIGN:
- Stateless: har request mein poori conversation history aati hai
- Yeh hum koi session maintain nahi karte
- Simple, clean, evaluator-friendly
"""
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from typing import List, Optional
import logging
import os
import sys
import time

# Path setup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.retriever import get_retriever
from agent.agent import process_conversation

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# FASTAPI APP INITIALIZATION
# ============================================================

app = FastAPI(
    title="SHL Assessment Recommender",
    description="Conversational agent for recommending SHL assessments to hiring managers",
    version="1.0.0"
)

# CORS middleware (agar frontend se call ho)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# PYDANTIC MODELS - Request/Response validation
# ============================================================

class Message(BaseModel):
    """Single conversation message"""
    role: str  # "user" ya "assistant"
    content: str
    
    @validator('role')
    def role_must_be_valid(cls, v):
        if v not in ['user', 'assistant']:
            raise ValueError('role must be "user" or "assistant"')
        return v
    
    @validator('content')
    def content_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('content cannot be empty')
        return v.strip()


class ChatRequest(BaseModel):
    """POST /chat ka request body"""
    messages: List[Message]
    
    @validator('messages')
    def messages_must_not_be_empty(cls, v):
        if not v:
            raise ValueError('messages list cannot be empty')
        # Max turns check (evaluator cap: 8)
        if len(v) > 16:  # 8 turns = 16 messages (user + assistant each)
            raise ValueError('Too many messages, conversation too long')
        return v


class Recommendation(BaseModel):
    """Single assessment recommendation"""
    name: str
    url: str
    test_type: str


class ChatResponse(BaseModel):
    """POST /chat ka response body - EXACTLY as specified in assignment"""
    reply: str
    recommendations: List[Recommendation]
    end_of_conversation: bool


class HealthResponse(BaseModel):
    """GET /health ka response"""
    status: str


# ============================================================
# STARTUP: Retriever initialize karo
# ============================================================

retriever = None

@app.on_event("startup")
async def startup_event():
    """
    App start hone pe retriever initialize karo.
    Catalog load karo aur index banao.
    """
    global retriever
    logger.info("Starting SHL Assessment Recommender...")
    retriever = get_retriever()
    logger.info(f"Retriever initialized with {len(retriever.catalog)} assessments")


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Evaluator pehle yeh call karta hai service wake up ke liye.
    Always 200 OK return karo.
    """
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    
    Request: { messages: [{role, content}, ...] }
    Response: { reply, recommendations, end_of_conversation }
    
    Stateless: har call mein poori history aati hai.
    """
    start_time = time.time()
    
    try:
        # Messages ko dict format mein convert karo
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]
        
        logger.info(f"Processing conversation with {len(messages)} messages")
        
        # Retriever check
        if retriever is None:
            raise HTTPException(
                status_code=503, 
                detail="Service not ready yet, please retry"
            )
        
        # Main processing
        result = process_conversation(messages, retriever)
        
        # Recommendations format karo
        recommendations = []
        for rec in result.get('recommendations', []):
            recommendations.append(Recommendation(
                name=rec.get('name', ''),
                url=rec.get('url', ''),
                test_type=rec.get('test_type', '')
            ))
        
        # Response banao
        response = ChatResponse(
            reply=result.get('reply', ''),
            recommendations=recommendations,
            end_of_conversation=bool(result.get('end_of_conversation', False))
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Response generated in {elapsed:.2f}s, {len(recommendations)} recommendations")
        
        return response
        
    except ValueError as e:
        # Validation errors
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    
    except Exception as e:
        # Unexpected errors
        logger.error(f"Error processing chat: {e}", exc_info=True)
        
        # Graceful fallback - schema maintain karo
        return ChatResponse(
            reply="I encountered an issue processing your request. Could you please rephrase or try again?",
            recommendations=[],
            end_of_conversation=False
        )


# ============================================================
# ROOT ENDPOINT (optional, helpful for debugging)
# ============================================================

@app.get("/")
async def root():
    """Root endpoint - API info"""
    return {
        "name": "SHL Assessment Recommender",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "chat": "POST /chat",
            "docs": "GET /docs"
        },
        "catalog_size": len(retriever.catalog) if retriever else "loading..."
    }


# ============================================================
# LOCAL DEVELOPMENT RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Development mein auto-reload
        log_level="info"
    )