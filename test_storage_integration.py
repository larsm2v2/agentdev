#!/usr/bin/env python3
"""
Test script for comprehensive Gmail storage integration.
Tests PostgreSQL, Qdrant, and Redis storage systems.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_storage_manager():
    """Test the Gmail Storage Manager directly"""
    print("\n" + "="*60)
    print("🧪 TESTING GMAIL STORAGE MANAGER")
    print("="*60)
    
    try:
        from src.core.gmail_storage_manager import GmailStorageManager
        
        # Initialize storage
        storage = GmailStorageManager()
        await storage.initialize()
        print("✅ Storage Manager initialized successfully")
        
        # Test database connection
        if storage.postgres_connected:
            print("✅ PostgreSQL connected")
        else:
            print("❌ PostgreSQL connection failed")
            
        if storage.qdrant_connected:
            print("✅ Qdrant connected")
        else:
            print("❌ Qdrant connection failed")
            
        if storage.redis_connected:
            print("✅ Redis connected")  
        else:
            print("❌ Redis connection failed")
            
        # Test API call storage
        print("\n📊 Testing API call logging...")
        api_call_id = await storage.log_api_call(
            endpoint="test_endpoint",
            method="GET",
            request_data={"test": "data"},
            emails_retrieved=5,
            processing_time=1.23
        )
        print(f"✅ API call logged with ID: {api_call_id}")
        
        # Test cache operations
        print("\n💾 Testing Redis cache...")
        test_key = "test_email_123"
        test_data = {"subject": "Test Email", "from": "test@example.com"}
        
        await storage.cache_email(test_key, test_data)
        cached_data = await storage.get_cached_email(test_key)
        
        if cached_data:
            print("✅ Redis cache working correctly")
        else:
            print("❌ Redis cache test failed")
            
        # Get usage stats
        print("\n📈 Getting storage statistics...")
        stats = await storage.get_api_usage_stats()
        print(f"✅ Storage stats retrieved:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
            
        await storage.close()
        print("✅ Storage Manager closed properly")
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("🔧 Make sure the container is rebuilt with sentence-transformers")
    except Exception as e:
        print(f"❌ Storage Manager test failed: {e}")

async def test_container_integration():
    """Test the container Gmail integration with storage"""
    print("\n" + "="*60)
    print("📦 TESTING CONTAINER GMAIL INTEGRATION")
    print("="*60)
    
    try:
        from src.core.container_gmail_categories import (
            get_container_batch_emails_with_storage,
            search_emails_by_content
        )
        
        # Test storage-enabled email retrieval
        print("📧 Testing storage-enabled email retrieval...")
        result = await get_container_batch_emails_with_storage(
            batch_size=5,
            query="in:inbox"
        )
        
        if result["status"] == "success":
            emails = result["emails"]
            storage_info = result.get("storage", {})
            print(f"✅ Retrieved {len(emails)} emails")
            print(f"📊 Storage enabled: {storage_info.get('storage_enabled', False)}")
            print(f"🔢 API Call ID: {storage_info.get('api_call_id', 'N/A')}")
            print(f"💾 Stored in: {', '.join(storage_info.get('stored_in', []))}")
        else:
            print(f"❌ Email retrieval failed: {result.get('message', 'Unknown error')}")
            
        # Test semantic search
        print("\n🔍 Testing semantic email search...")
        search_results = await search_emails_by_content("meeting schedule", limit=3)
        print(f"✅ Semantic search returned {len(search_results)} results")
        
        for i, result in enumerate(search_results[:2], 1):
            print(f"   {i}. {result.get('subject', 'No subject')[:50]}... (Score: {result.get('score', 'N/A')})")
            
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("🔧 Container integration not available")
    except Exception as e:
        print(f"❌ Container integration test failed: {e}")

async def test_api_endpoints():
    """Test the API endpoints via HTTP requests"""
    print("\n" + "="*60)
    print("🌐 TESTING API ENDPOINTS")
    print("="*60)
    
    try:
        import aiohttp
        
        base_url = "http://localhost:8001"
        
        async with aiohttp.ClientSession() as session:
            # Test storage stats endpoint
            print("📊 Testing storage stats endpoint...")
            async with session.get(f"{base_url}/api/storage/stats") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Storage stats endpoint working")
                    print(f"   Status: {data.get('status', 'unknown')}")
                else:
                    print(f"❌ Storage stats endpoint failed: {response.status}")
                    
            # Test storage-enabled email retrieval
            print("\n📧 Testing storage-enabled email endpoint...")
            async with session.get(f"{base_url}/api/functions/cataloging/batch-emails-with-storage?batch_size=3") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Storage-enabled email endpoint working")
                    print(f"   Retrieved: {len(data.get('emails', []))} emails")
                    print(f"   Storage info: {data.get('storage', {})}")
                else:
                    print(f"❌ Storage-enabled email endpoint failed: {response.status}")
                    
            # Test semantic search endpoint  
            print("\n🔍 Testing semantic search endpoint...")
            async with session.post(
                f"{base_url}/api/storage/search",
                params={"query": "important meeting", "limit": 2}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Semantic search endpoint working")
                    print(f"   Found: {data.get('count', 0)} results")
                else:
                    print(f"❌ Semantic search endpoint failed: {response.status}")
                    
    except ImportError:
        print("❌ aiohttp not available - skipping HTTP tests")
        print("💡 Install aiohttp to test API endpoints: pip install aiohttp")
    except Exception as e:
        print(f"❌ API endpoint tests failed: {e}")

async def main():
    """Run comprehensive storage integration tests"""
    print("🚀 Gmail Storage Integration Test Suite")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Storage Manager
    await test_storage_manager()
    
    # Test 2: Container Integration
    await test_container_integration()
    
    # Test 3: API Endpoints (requires server running)
    await test_api_endpoints()
    
    print("\n" + "="*60)
    print("✨ TEST SUITE COMPLETED")
    print("="*60)
    print("📝 Summary:")
    print("   1. Storage Manager: Direct database/cache testing")
    print("   2. Container Integration: Gmail API with storage")
    print("   3. API Endpoints: HTTP interface testing")
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main())
