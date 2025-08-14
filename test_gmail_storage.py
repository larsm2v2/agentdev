#!/usr/bin/env python3
"""
Test script for Gmail Storage Integration
Tests the comprehensive storage system with PostgreSQL, Qdrant, and Redis
"""

import asyncio
import json
from src.core.container_gmail_categories import (
    get_container_batch_emails_with_storage,
    get_container_gmail_categories_with_storage,
    search_emails_by_content
)

async def test_storage_integration():
    """Test the storage-enabled Gmail functions"""
    
    print("🚀 Testing Gmail Storage Integration")
    print("=" * 50)
    
    # Test 1: Get categories with storage
    print("\n📋 Test 1: Gmail Categories with Storage")
    try:
        categories_result = await get_container_gmail_categories_with_storage()
        print(f"✅ Categories retrieved: {categories_result.get('status')}")
        if categories_result.get('storage'):
            print(f"📊 Storage info: {categories_result['storage']}")
        else:
            print("⚠️ No storage info found")
    except Exception as e:
        print(f"❌ Categories test failed: {e}")
    
    # Test 2: Get batch emails with storage
    print("\n📧 Test 2: Batch Emails with Storage")
    try:
        emails_result = await get_container_batch_emails_with_storage(batch_size=10, query="in:inbox")
        print(f"✅ Emails retrieved: {emails_result.get('status')}")
        if emails_result.get('emails'):
            print(f"📧 Email count: {len(emails_result['emails'])}")
        if emails_result.get('storage'):
            print(f"📊 Storage info: {emails_result['storage']}")
        else:
            print("⚠️ No storage info found")
    except Exception as e:
        print(f"❌ Emails test failed: {e}")
    
    # Test 3: Semantic search (if available)
    print("\n🔍 Test 3: Semantic Search")
    try:
        search_results = await search_emails_by_content("meeting schedule", limit=5)
        if search_results:
            print(f"✅ Semantic search results: {len(search_results)} emails found")
            for i, email in enumerate(search_results[:3]):
                print(f"   {i+1}. {email.get('subject', 'No Subject')} (score: {email.get('similarity_score', 0):.3f})")
        else:
            print("⚠️ No semantic search results (may not be available)")
    except Exception as e:
        print(f"❌ Semantic search test failed: {e}")
    
    print("\n🎯 Storage Integration Test Complete!")

async def test_storage_manager_directly():
    """Test the storage manager directly"""
    print("\n🔧 Testing Storage Manager Directly")
    print("-" * 40)
    
    try:
        from src.core.gmail_storage_manager import GmailStorageManager
        
        # Initialize storage manager
        storage = GmailStorageManager()
        initialized = await storage.initialize()
        
        if initialized:
            print("✅ Storage manager initialized successfully")
            
            # Test API usage stats
            stats = await storage.get_api_usage_stats()
            print(f"📊 API Usage Stats: {json.dumps(stats, indent=2, default=str)}")
            
        else:
            print("❌ Storage manager initialization failed")
            
        await storage.close()
        
    except Exception as e:
        print(f"❌ Storage manager test failed: {e}")

if __name__ == "__main__":
    print("Gmail Storage Integration Test")
    print("=" * 60)
    
    # Run the tests
    asyncio.run(test_storage_integration())
    asyncio.run(test_storage_manager_directly())
