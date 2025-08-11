# Core modules for Email Librarian
"""
Core Email Librarian modules providing LLM integration, email agents, and server functionality.

This package contains:
- direct_llm_providers: Direct LLM API integration without LangChain
- modern_email_agents: CrewAI-based email processing agents
- simple_email_agents: Simplified email agent system
- email_agents: Legacy email processing agents
- enhanced_email_librarian_server: Main FastAPI server
"""

# Import core classes for easy access
try:
    from .direct_llm_providers import MultiLLMManager, LLMProvider
    from .modern_email_agents import ModernEmailAgents
    from .simple_email_agents import SimpleEmailAgentSystem
    
    __all__ = [
        'MultiLLMManager',
        'LLMProvider', 
        'ModernEmailAgents',
        'SimpleEmailAgentSystem'
    ]
except ImportError as e:
    # Handle import errors gracefully during development
    print(f"Warning: Some core modules could not be imported: {e}")
    __all__ = []

__version__ = "0.1.0"
