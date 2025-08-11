#!/usr/bin/env python3
"""
Direct LLM Provider Integration - No LangChain Dependencies
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from dotenv import load_dotenv
import openai
import asyncio

# Load environment variables
load_dotenv(override=True)

class LLMProvider(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text response from prompt"""
        pass
    
    @abstractmethod
    async def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for text"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and configured"""
        pass

class OpenAIProvider(BaseLLMProvider):
    """Direct OpenAI API provider"""
    
    def __init__(self, model: str = "gpt-4-turbo-preview", **kwargs):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = model
        self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
        
        if self.api_key:
            openai.api_key = self.api_key
    
    def is_available(self) -> bool:
        """Check if OpenAI is configured"""
        return bool(self.api_key)
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using OpenAI API"""
        try:
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", 1500),
                temperature=kwargs.get("temperature", 0.7),
                **{k: v for k, v in kwargs.items() if k in ["top_p", "frequency_penalty", "presence_penalty"]}
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return f"Error generating response: {str(e)}"
    
    async def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings using OpenAI API"""
        try:
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            response = await client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            print(f"OpenAI embeddings error: {e}")
            return []

class GeminiProvider(BaseLLMProvider):
    """Google Gemini API provider"""
    
    def __init__(self, model: str = "gemini-pro", **kwargs):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model = model
    
    def is_available(self) -> bool:
        """Check if Gemini is configured"""
        return bool(self.api_key)
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using Gemini API"""
        if not self.api_key:
            print("❌ No Google API key found")
            return "No Google API key configured"
        
        # Try multiple approaches for different Google AI library versions
        
        # Approach 1: Try the new google-genai SDK
        try:
            from google import genai
            
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            return str(response.text) if hasattr(response, 'text') else str(response)
            
        except ImportError:
            print("⚠️ New google-genai SDK not available, trying old API...")
        except Exception as e:
            print(f"⚠️ New API failed: {e}, trying old API...")
        
        # Approach 2: Try the older google.generativeai with dynamic attribute access
        try:
            import google.generativeai as genai
            
            # Use dynamic attribute access to avoid Pylance errors
            configure_func = getattr(genai, 'configure', None)
            GenerativeModel = getattr(genai, 'GenerativeModel', None)
            
            if configure_func and GenerativeModel:
                configure_func(api_key=self.api_key)
                model = GenerativeModel(self.model)
                
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt
                )
                
                return response.text if hasattr(response, 'text') else str(response)
            else:
                raise AttributeError("Required functions not available in google.generativeai")
                
        except ImportError:
            print("⚠️ google.generativeai not available")
        except Exception as e:
            print(f"⚠️ Old API failed: {e}")
        
        # Approach 3: Fallback to OpenAI
        print("⚠️ All Gemini approaches failed, falling back to OpenAI")
        openai_provider = OpenAIProvider()
        if openai_provider.is_available():
            return await openai_provider.generate_text(prompt, **kwargs)
        
        return "Error: Gemini API not available and no fallback provider configured"
    
    async def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings - currently fallback to OpenAI as Gemini embeddings are complex"""
        print("⚠️ Using OpenAI for embeddings (Gemini embeddings require complex setup)")
        openai_provider = OpenAIProvider()
        if openai_provider.is_available():
            return await openai_provider.generate_embeddings(text)
        return []

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider"""
    
    def __init__(self, model: str = "claude-3-sonnet-20240229", **kwargs):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = model
    
    def is_available(self) -> bool:
        """Check if Anthropic is configured"""
        return bool(self.api_key)
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using Anthropic API"""
        try:
            import anthropic
            
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            
            response = await client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1500),
                temperature=kwargs.get("temperature", 0.7),
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Handle different types of content blocks
            if response.content and len(response.content) > 0:
                content_block = response.content[0]
                # Use getattr with fallback to handle different content block types
                return getattr(content_block, 'text', str(content_block))
            else:
                return "No response content received"
            
        except Exception as e:
            print(f"Anthropic API error: {e}")
            return f"Error generating response: {str(e)}"
    
    async def generate_embeddings(self, text: str) -> List[float]:
        """Anthropic doesn't provide embeddings - fallback to OpenAI"""
        openai_provider = OpenAIProvider()
        if openai_provider.is_available():
            return await openai_provider.generate_embeddings(text)
        return []

class LLMProviderFactory:
    """Factory for creating LLM providers"""
    
    _providers = {
        LLMProvider.OPENAI: OpenAIProvider,
        LLMProvider.GEMINI: GeminiProvider,
        LLMProvider.ANTHROPIC: AnthropicProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_type: Optional[LLMProvider] = None, **kwargs) -> BaseLLMProvider:
        """Create LLM provider instance"""
        
        if provider_type is None:
            # Auto-detect best available provider
            provider_type = cls.get_best_provider()
        
        provider_class = cls._providers.get(provider_type)
        if not provider_class:
            raise ValueError(f"Unsupported provider: {provider_type}")
        
        return provider_class(**kwargs)
    
    @classmethod
    def get_best_provider(cls) -> LLMProvider:
        """Get the best available provider based on API keys"""
        
        # Check in order of preference - OpenAI first, then Anthropic, then Gemini
        for provider_type in [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GEMINI]:
            provider_class = cls._providers[provider_type]
            temp_provider = provider_class()
            
            if temp_provider.is_available():
                print(f"✅ Using {provider_type.value} provider")
                return provider_type
        
        print("⚠️ No LLM providers available - check your API keys")
        return LLMProvider.OPENAI  # Default fallback
    
    @classmethod
    def list_available_providers(cls) -> List[LLMProvider]:
        """List all available providers"""
        available = []
        
        for provider_type, provider_class in cls._providers.items():
            temp_provider = provider_class()
            if temp_provider.is_available():
                available.append(provider_type)
        
        return available

class MultiLLMManager:
    """Manager for handling multiple LLM providers"""
    
    def __init__(self, provider_type: Optional[LLMProvider] = None, **kwargs):
        """Initialize with specified or auto-detected provider"""
        self.provider = LLMProviderFactory.create_provider(provider_type, **kwargs)
        self.provider_type = provider_type or LLMProviderFactory.get_best_provider()
        
        print(f"🤖 MultiLLM Manager initialized with {self.provider_type.value}")
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate text response"""
        return await self.provider.generate_text(prompt, **kwargs)
    
    async def get_embeddings(self, text: str) -> List[float]:
        """Get text embeddings"""
        return await self.provider.generate_embeddings(text)
    
    def is_available(self) -> bool:
        """Check if current provider is available"""
        return self.provider.is_available()

# Convenience functions for quick usage
async def generate_text(prompt: str, provider: Optional[LLMProvider] = None, **kwargs) -> str:
    """Quick function to generate text"""
    manager = MultiLLMManager(provider)
    return await manager.generate_response(prompt, **kwargs)

async def get_embeddings(text: str, provider: Optional[LLMProvider] = None) -> List[float]:
    """Quick function to get embeddings"""
    manager = MultiLLMManager(provider)
    return await manager.get_embeddings(text)

def test_providers():
    """Test all available providers"""
    print("🧪 Testing LLM Providers...")
    
    available = LLMProviderFactory.list_available_providers()
    print(f"📋 Available providers: {[p.value for p in available]}")
    
    if not available:
        print("❌ No providers available - check your API keys")
        return
    
    async def run_tests():
        for provider_type in available:
            print(f"\n🔧 Testing {provider_type.value}...")
            try:
                manager = MultiLLMManager(provider_type)
                
                # Test text generation
                response = await manager.generate_response(
                    "What is the capital of France? Answer in one sentence.",
                    max_tokens=50
                )
                print(f"✅ Text generation: {response[:100]}...")
                
                # Test embeddings
                embeddings = await manager.get_embeddings("Test text")
                print(f"✅ Embeddings: {len(embeddings)} dimensions")
                
            except Exception as e:
                print(f"❌ Error testing {provider_type.value}: {e}")

    asyncio.run(run_tests())

if __name__ == "__main__":
    test_providers()
