#!/usr/bin/env python3
"""
Modern Email Agents using CrewAI - No LangChain Dependencies
"""

import os
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from dotenv import load_dotenv

# CrewAI imports
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool

# Direct LLM provider
from .direct_llm_providers import MultiLLMManager, LLMProvider

# Force reload environment variables
load_dotenv(override=True)

class EmailClassificationTool(BaseTool):
    """Tool for classifying emails using direct LLM integration"""
    
    name: str = "email_classifier"
    description: str = "Classify emails into appropriate categories based on content"
    
    def __init__(self, llm_manager: MultiLLMManager):
        super().__init__(name=self.name, description=self.description)
        self.llm_manager = llm_manager
    
    async def _run(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify email content"""
        
        # Build classification prompt
        prompt = f"""
        Analyze this email and classify it into the most appropriate category:
        
        Subject: {email_data.get('subject', 'No subject')}
        From: {email_data.get('sender', 'Unknown sender')}
        Content: {email_data.get('body', 'No content')[:500]}...

        Categories: {email_data.get('categories', [])}

        Respond with JSON format:
        {{
            "category": "category_name",
            "confidence": 0.95,
            "reasoning": "Brief explanation of why this category was chosen"
        }}
        """
        
        try:
            response = await self.llm_manager.generate_response(prompt, max_tokens=300)
            
            # Try to parse JSON response
            if response.strip().startswith('{'):
                result = json.loads(response.strip())
            else:
                # Fallback parsing if not JSON
                result = {
                    "category": "other",
                    "confidence": 0.5,
                    "reasoning": "Unable to parse classification response"
                }
            
            return result
            
        except Exception as e:
            return {
                "category": "other",
                "confidence": 0.1,
                "reasoning": f"Classification error: {str(e)}"
            }

class EmailSummaryTool(BaseTool):
    """Tool for generating email summaries"""
    
    name: str = "email_summarizer"
    description: str = "Generate concise summaries of email content"
    
    def __init__(self, llm_manager: MultiLLMManager):
        super().__init__(name=self.name, description=self.description)
        self.llm_manager = llm_manager
    
    async def _run(self, email_data: Dict[str, Any]) -> str:
        """Generate email summary"""
        
        prompt = f"""
        Summarize this email in 1-2 sentences:
        
        Subject: {email_data.get('subject', 'No subject')}
        From: {email_data.get('sender', 'Unknown sender')}
        Content: {email_data.get('body', 'No content')[:1000]}
        
        Provide a clear, concise summary of the main points.
        """
        
        try:
            return await self.llm_manager.generate_response(prompt, max_tokens=200)
        except Exception as e:
            return f"Summary generation failed: {str(e)}"

class EmailActionTool(BaseTool):
    """Tool for suggesting email actions"""
    
    name: str = "email_action_suggester"
    description: str = "Suggest appropriate actions for emails"
    
    def __init__(self, llm_manager: MultiLLMManager):
        super().__init__(name=self.name, description=self.description)
        self.llm_manager = llm_manager
    
    async def _run(self, email_data: Dict[str, Any]) -> List[str]:
        """Suggest actions for email"""
        
        prompt = f"""
        Based on this email, suggest appropriate actions:
        
        Subject: {email_data.get('subject', 'No subject')}
        From: {email_data.get('sender', 'Unknown sender')}
        Content: {email_data.get('body', 'No content')[:500]}
        
        Suggest 1-3 specific actions from these options:
        - reply_required: Needs a response
        - archive: Can be archived
        - follow_up: Schedule follow-up
        - mark_important: Mark as important
        - forward: Should be forwarded
        - delete: Can be deleted
        - calendar_event: Create calendar event
        - task_create: Create task/reminder
        
        Return as JSON array: ["action1", "action2"]
        """
        
        try:
            response = await self.llm_manager.generate_response(prompt, max_tokens=100)
            
            # Try to parse JSON response
            if response.strip().startswith('['):
                return json.loads(response.strip())
            else:
                # Fallback - extract actions from text
                actions = []
                for action in ["reply_required", "archive", "follow_up", "mark_important"]:
                    if action in response.lower():
                        actions.append(action)
                return actions or ["archive"]
                
        except Exception as e:
            return ["archive"]  # Safe default

class ModernEmailAgents:
    """Modern email processing agents using CrewAI"""
    
    def __init__(self, provider_type: Optional[LLMProvider] = None, **llm_kwargs):
        """Initialize with LLM provider"""
        
        # Initialize direct LLM manager
        self.llm_manager = MultiLLMManager(provider_type, **llm_kwargs)
        
        # Initialize tools
        self.classification_tool = EmailClassificationTool(self.llm_manager)
        self.summary_tool = EmailSummaryTool(self.llm_manager)
        self.action_tool = EmailActionTool(self.llm_manager)
        
        # Create specialized agents
        self.setup_agents()
        
        print("✅ Modern email agents initialized successfully!")
    
    def setup_agents(self):
        """Setup CrewAI agents for different email tasks"""
        
        # Email Classification Agent
        self.classifier_agent = Agent(
            role='Email Classifier',
            goal='Accurately classify emails into appropriate categories',
            backstory='You are an expert email organizer with years of experience categorizing different types of emails.',
            tools=[self.classification_tool],
            verbose=True,
            allow_delegation=False
        )
        
        # Email Summarization Agent
        self.summarizer_agent = Agent(
            role='Email Summarizer',
            goal='Create concise, informative summaries of email content',
            backstory='You are skilled at extracting key information and creating clear, actionable summaries.',
            tools=[self.summary_tool],
            verbose=True,
            allow_delegation=False
        )
        
        # Email Action Agent
        self.action_agent = Agent(
            role='Email Action Specialist',
            goal='Suggest appropriate actions based on email content and urgency',
            backstory='You are an expert at email workflow optimization and productivity.',
            tools=[self.action_tool],
            verbose=True,
            allow_delegation=False
        )
    
    async def process_email_complete(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Complete email processing pipeline"""
        
        # Create tasks for the crew
        classification_task = Task(
            description=f"Classify this email: {email_data.get('subject', 'No subject')}",
            agent=self.classifier_agent,
            expected_output="JSON with category, confidence, and reasoning"
        )
        
        summary_task = Task(
            description=f"Summarize this email: {email_data.get('subject', 'No subject')}",
            agent=self.summarizer_agent,
            expected_output="Concise 1-2 sentence summary"
        )
        
        action_task = Task(
            description=f"Suggest actions for this email: {email_data.get('subject', 'No subject')}",
            agent=self.action_agent,
            expected_output="List of suggested actions"
        )
        
        # Create and run crew
        crew = Crew(
            agents=[self.classifier_agent, self.summarizer_agent, self.action_agent],
            tasks=[classification_task, summary_task, action_task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            # Run the crew
            results = crew.kickoff()
            
            # Process results
            classification = await self.classification_tool._run(email_data)
            summary = await self.summary_tool._run(email_data)
            actions = await self.action_tool._run(email_data)
            
            return {
                "classification": classification,
                "summary": summary,
                "suggested_actions": actions,
                "processed_at": datetime.now().isoformat(),
                "success": True
            }
            
        except Exception as e:
            print(f"Error in email processing crew: {e}")
            return {
                "classification": {"category": "other", "confidence": 0.1, "reasoning": f"Processing error: {str(e)}"},
                "summary": f"Processing failed: {str(e)}",
                "suggested_actions": ["archive"],
                "processed_at": datetime.now().isoformat(),
                "success": False,
                "error": str(e)
            }
    
    async def classify_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Quick email classification"""
        return await self.classification_tool._run(email_data)
    
    async def summarize_email(self, email_data: Dict[str, Any]) -> str:
        """Quick email summarization"""
        return await self.summary_tool._run(email_data)
    
    async def suggest_actions(self, email_data: Dict[str, Any]) -> List[str]:
        """Quick action suggestions"""
        return await self.action_tool._run(email_data)
    
    async def batch_process_emails(self, emails: List[Dict[str, Any]], batch_size: int = 5) -> List[Dict[str, Any]]:
        """Process multiple emails in batches"""
        
        results = []
        
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            batch_results = []
            
            print(f"📧 Processing batch {i//batch_size + 1} ({len(batch)} emails)")
            
            for email in batch:
                try:
                    result = await self.process_email_complete(email)
                    batch_results.append({
                        "email_id": email.get("id", f"email_{i}"),
                        "result": result
                    })
                except Exception as e:
                    batch_results.append({
                        "email_id": email.get("id", f"email_{i}"),
                        "result": {
                            "success": False,
                            "error": str(e),
                            "processed_at": datetime.now().isoformat()
                        }
                    })
            
            results.extend(batch_results)
        
        return results

# Convenience functions
async def classify_email_quick(email_data: Dict[str, Any], provider: Optional[LLMProvider] = None) -> Dict[str, Any]:
    """Quick email classification function"""
    agents = ModernEmailAgents(provider)
    return await agents.classify_email(email_data)

async def process_email_full(email_data: Dict[str, Any], provider: Optional[LLMProvider] = None) -> Dict[str, Any]:
    """Full email processing function"""
    agents = ModernEmailAgents(provider)
    return await agents.process_email_complete(email_data)

def test_email_agents():
    """Test the email agents system"""
    import asyncio
    
    print("🧪 Testing Modern Email Agents...")
    
    # Sample email data
    test_email = {
        "id": "test_001",
        "subject": "Project Update: Q4 Marketing Campaign",
        "sender": "marketing@company.com",
        "body": "Hi team, I wanted to provide an update on our Q4 marketing campaign. We've seen a 25% increase in engagement rates compared to Q3. The campaign is performing well across all channels. We should schedule a meeting next week to discuss the final push for the holiday season. Please let me know your availability.",
        "timestamp": datetime.now().isoformat()
    }
    
    async def run_test():
        try:
            agents = ModernEmailAgents()
            
            print("\n📋 Testing email classification...")
            classification = await agents.classify_email(test_email)
            print(f"Classification: {classification}")
            
            print("\n📝 Testing email summarization...")
            summary = await agents.summarize_email(test_email)
            print(f"Summary: {summary}")
            
            print("\n⚡ Testing action suggestions...")
            actions = await agents.suggest_actions(test_email)
            print(f"Actions: {actions}")
            
            print("\n🔄 Testing complete processing...")
            result = await agents.process_email_complete(test_email)
            print(f"Complete result: {json.dumps(result, indent=2)}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    asyncio.run(run_test())

if __name__ == "__main__":
    test_email_agents()
