"""
Gmail Storage Integration Usage Examples
Demonstrates how to use the comprehensive storage system
"""

import asyncio
from src.core.container_gmail_categories import (
    get_container_gmail_categories_with_storage
)
# If get_container_batch_emails_with_storage is needed, ensure it is defined and exported in container_gmail_categories.py
# Otherwise, replace its usage with the correct function name as defined in that module.

# =============================================================================
# Example 1: Basic Email Retrieval with Storage
# =============================================================================

async def example_retrieve_emails_with_storage():
    """
    Retrieve emails and store them in PostgreSQL, Qdrant, and Redis
    
    This function will:
    1. Check Redis cache for existing results
    2. Make Gmail API calls if not cached
    3. Store emails in PostgreSQL for structured queries
    4. Store embeddings in Qdrant for semantic search
    5. Cache results in Redis for fast access
    """
    print("📧 Retrieving emails with full storage integration...")
    
    result = await get_container_batch_emails_with_storage(
        batch_size=20,  # Get 20 emails
        query="in:inbox"  # From inbox
    )
    
    if result["status"] == "success":
        print(f"✅ Retrieved {len(result['emails'])} emails")
        
        # Storage information
        if "storage" in result:
            storage_info = result["storage"]
            print(f"📊 Storage details:")
            print(f"   API Call ID: {storage_info.get('api_call_id')}")
            print(f"   Stored in: {', '.join(storage_info.get('stored_in', []))}")
            print(f"   Timestamp: {storage_info.get('storage_timestamp')}")
        
        # Show some email details
        for i, email in enumerate(result["emails"][:3]):
            print(f"   {i+1}. {email.get('subject', 'No Subject')}")
            print(f"      From: {email.get('from', 'Unknown')}")
            print(f"      Labels: {email.get('labelIds', [])}")
    
    return result

# =============================================================================
# Example 2: Gmail Categories with Storage
# =============================================================================

async def example_retrieve_categories_with_storage():
    """
    Retrieve Gmail labels/categories and store them
    
    This function will:
    1. Check Redis cache for recent category data
    2. Make Gmail API call if not cached
    3. Store label information in PostgreSQL
    4. Cache results in Redis
    """
    print("🏷️ Retrieving Gmail categories with storage...")
    
    result = await get_container_gmail_categories_with_storage()
    
    if result["status"] == "success":
        categories = result["categories"]
        print(f"✅ Retrieved {categories['total_count']} labels")
        print(f"   System labels: {len(categories['system_labels'])}")
        print(f"   User labels: {len(categories['user_labels'])}")
        
        # Show some custom labels
        if categories["user_labels"]:
            print("   Custom labels:")
            for label in categories["user_labels"][:5]:
                print(f"      - {label['name']} ({label.get('messagesTotal', 0)} messages)")
    
    return result

# =============================================================================
# Example 3: Semantic Email Search
# =============================================================================

async def example_semantic_search():
    """
    Search emails using semantic similarity
    
    This requires emails to be stored with embeddings first
    """
    print("🔍 Performing semantic email search...")
    
    # Search for emails about meetings
    search_queries = [
        "meeting schedule",
        "project deadline",
        "payment invoice",
        "vacation time off"
    ]
    
    for query in search_queries:
        print(f"\n🔎 Searching for: '{query}'")
        results = await search_emails_by_content(query, limit=3)
        
        if results:
            print(f"   Found {len(results)} similar emails:")
            for i, email in enumerate(results):
                score = email.get('similarity_score', 0)
                subject = email.get('subject', 'No Subject')
                sender = email.get('sender', 'Unknown')
                print(f"      {i+1}. {subject} (score: {score:.3f})")
                print(f"         From: {sender}")
        else:
            print("   No similar emails found")

# =============================================================================
# Example 4: API Usage Monitoring
# =============================================================================

async def example_monitor_api_usage():
    """
    Monitor Gmail API usage and efficiency
    """
    print("📊 Monitoring API usage...")
    
    try:
        from src.core.gmail_storage_manager import GmailStorageManager
        
        storage = GmailStorageManager()
        await storage.initialize()
        
        stats = await storage.get_api_usage_stats()
        
        print("📈 API Usage Statistics:")
        print(f"   Today's API calls: {stats.get('today_api_calls', 0)}")
        print(f"   Emails stored today: {stats.get('today_emails_stored', 0)}")
        print(f"   Avg emails per call: {stats.get('avg_emails_per_call', 0)}")
        
        # Storage system status
        storage_status = stats.get('storage_status', {})
        print("\n🔧 Storage System Status:")
        print(f"   PostgreSQL: {'✅' if storage_status.get('postgresql') else '❌'}")
        print(f"   Qdrant: {'✅' if storage_status.get('qdrant') else '❌'}")
        print(f"   Redis: {'✅' if storage_status.get('redis') else '❌'}")
        print(f"   Embeddings: {'✅' if storage_status.get('embeddings') else '❌'}")
        
        await storage.close()
        
    except Exception as e:
        print(f"❌ Error monitoring API usage: {e}")

# =============================================================================
# Example 5: Smart Caching Strategy
# =============================================================================

async def example_smart_caching():
    """
    Demonstrate smart caching to minimize API calls
    """
    print("⚡ Demonstrating smart caching...")
    
    # First call - will hit Gmail API
    print("\n📞 First call (will use Gmail API):")
    start_time = asyncio.get_event_loop().time()
    result1 = await get_container_batch_emails_with_storage(batch_size=10, query="in:inbox")
    first_call_time = asyncio.get_event_loop().time() - start_time
    print(f"   Time: {first_call_time:.2f}s")
    
    # Second call - should use cache
    print("\n⚡ Second call (should use Redis cache):")
    start_time = asyncio.get_event_loop().time()
    result2 = await get_container_batch_emails_with_storage(batch_size=10, query="in:inbox")
    second_call_time = asyncio.get_event_loop().time() - start_time
    print(f"   Time: {second_call_time:.2f}s")
    
    if second_call_time < first_call_time * 0.5:
        print("✅ Caching is working! Second call was much faster.")
        speedup = first_call_time / second_call_time
        print(f"   Speedup: {speedup:.1f}x faster")
    else:
        print("⚠️ Cache may not be working as expected")

# =============================================================================
# Main Demo Function
# =============================================================================

async def run_storage_examples():
    """Run all storage integration examples"""
    
    print("🚀 Gmail Storage Integration Examples")
    print("=" * 60)
    
    examples = [
        ("Email Retrieval with Storage", example_retrieve_emails_with_storage),
        ("Categories with Storage", example_retrieve_categories_with_storage),
        ("Semantic Search", example_semantic_search),
        ("API Usage Monitoring", example_monitor_api_usage),
        ("Smart Caching Demo", example_smart_caching)
    ]
    
    for title, example_func in examples:
        print(f"\n🎯 {title}")
        print("-" * 40)
        try:
            await example_func()
        except Exception as e:
            print(f"❌ Example failed: {e}")
        print()
    
    print("🎉 All examples completed!")

if __name__ == "__main__":
    # Run the examples
    asyncio.run(run_storage_examples())
