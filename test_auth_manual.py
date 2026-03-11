"""Test authentication manually."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal, engine, Base
from app.models import User
from app.utils.security import hash_password, create_access_token, verify_password

# Create tables
print("Creating tables...")
Base.metadata.create_all(bind=engine)

# Create test user
db = SessionLocal()
try:
    # Check if demo user exists
    existing = db.query(User).filter(User.email == "demo@pharma.com").first()
    if existing:
        print(f"✓ Demo user exists: {existing.email}")
        print(f"  ID: {existing.id}")
        print(f"  Password hash: {existing.password_hash[:20]}...")
        
        # Test password verification
        test_pwd = "demo1234"
        is_valid = verify_password(test_pwd, existing.password_hash)
        print(f"  Password test: {'✓ Valid' if is_valid else '✗ Invalid'}")
        
        # Create token
        token = create_access_token(str(existing.id))
        print(f"  Token: {token[:50]}...")
    else:
        print("✗ Demo user not found. Run seed_sample.py first.")
        
finally:
    db.close()
