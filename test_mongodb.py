"""
MongoDB Connection Test Script
Run this to verify your MongoDB Atlas connection
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MONGODB_URI = os.environ.get('MONGODB_URI', '').strip()
MONGODB_DB = os.environ.get('MONGODB_DB', 'gal')

print("=" * 60)
print("MongoDB Connection Test")
print("=" * 60)

if not MONGODB_URI:
    print("❌ ERROR: MONGODB_URI not found in .env file")
    print("   Please ensure your .env file contains:")
    print("   MONGODB_URI=mongodb+srv://...")
    exit(1)

print(f"📋 Database: {MONGODB_DB}")
print(f"🔗 Connecting to MongoDB...")

try:
    from pymongo import MongoClient
    
    # Connect with timeout
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    
    # Test connection
    client.admin.command('ping')
    
    print("✅ Successfully connected to MongoDB!")
    
    # Get database and list collections
    db = client[MONGODB_DB]
    collections = db.list_collection_names()
    
    print(f"📚 Database collections: {collections if collections else 'None (empty database)'}")
    
    # Close connection
    client.close()
    print("\n✅ Connection test passed!")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\n⚠️  Troubleshooting tips:")
    print("   1. Check that your password is correct in .env file")
    print("   2. Verify the username is: 24p31a05i6_db_user")
    print("   3. Ensure MongoDB Atlas IP whitelist includes your IP")
    print("   4. Check your internet connection")
    exit(1)
