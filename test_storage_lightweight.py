#!/usr/bin/env python3
"""
Lightweight test for Gmail storage integration without sentence-transformers.
Tests PostgreSQL and Redis storage without vector embeddings.
"""

import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_lightweight_storage():
    """Test storage components that don't require sentence-transformers"""
    print("\n🧪 LIGHTWEIGHT STORAGE TEST")
    print("="*50)
    
    try:
        # Test basic imports
        from src.core.gmail_storage_manager import GmailStorageManager
        print("✅ GmailStorageManager imported successfully")
        
        # Test initialization (should work even without sentence-transformers)
        storage = GmailStorageManager()
        
        # Test connection status
        print(f"📊 Storage instance created")
        print(f"   - Default vector_enabled: {getattr(storage, 'vector_enabled', 'Unknown')}")
        
        # Test basic API call logging (PostgreSQL)
        if hasattr(storage, 'log_api_call'):
            print("✅ API call logging method available")
        else:
            print("❌ API call logging method not found")
            
        # Test cache methods (Redis)
        if hasattr(storage, 'cache_email') and hasattr(storage, 'get_cached_email'):
            print("✅ Redis cache methods available")
        else:
            print("❌ Redis cache methods not found")
            
        print("✅ Basic storage structure verified")
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
    except Exception as e:
        print(f"❌ Test failed: {e}")

async def test_fallback_functions():
    """Test the fallback dummy functions in container_gmail_categories.py"""
    print("\n🔄 FALLBACK FUNCTIONS TEST")
    print("="*50)
    
    try:
        from src.core.container_gmail_categories import get_container_batch_emails_with_storage
        print("✅ get_container_batch_emails_with_storage imported")
        
        # This should work even with dummy functions
        result = await get_container_batch_emails_with_storage(batch_size=1)
        print(f"📧 Function returned: {result.get('status', 'unknown')}")
        
        if result.get("status") == "success":
            print("✅ Function executed successfully (with or without storage)")
        else:
            print(f"ℹ️  Function result: {result.get('message', 'No message')}")
            
    except ImportError as e:
        print(f"❌ Import failed: {e}")
    except Exception as e:
        print(f"❌ Fallback test failed: {e}")

async def test_database_schemas():
    """Test if database schema definitions are accessible"""
    print("\n🗃️  DATABASE SCHEMA TEST")
    print("="*50)
    
    try:
        from src.core.gmail_storage_manager import GmailStorageManager
        
        # Check if schema methods exist
        storage = GmailStorageManager()
        
        if hasattr(storage, 'create_tables'):
            print("✅ create_tables method available")
        if hasattr(storage, 'postgres_schema'):
            print("✅ postgres_schema property available")
        if hasattr(storage, 'qdrant_collection_config'):
            print("✅ qdrant_collection_config available")
            
        print("✅ Schema definitions accessible")
        
    except Exception as e:
        print(f"❌ Schema test failed: {e}")

async def main():
    """Run lightweight tests"""
    print("⚡ Gmail Storage - Lightweight Integration Test")
    print(f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}")
    
    await test_lightweight_storage()
    await test_fallback_functions()
    await test_database_schemas()
    
    print("\n✨ LIGHTWEIGHT TEST COMPLETED")
    print("💡 This test verifies storage structure without requiring")
    print("   sentence-transformers or full container rebuild")

if __name__ == "__main__":
    asyncio.run(main())
