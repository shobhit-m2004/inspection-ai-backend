"""Quick auth test - run after starting the server."""
import requests

BASE_URL = "http://localhost:8000"

print("Testing Authentication...")
print("=" * 50)

# Test 1: Register new user
print("\n1. Testing registration...")
try:
    resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "test1234"
        }
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 201:
        print(f"   ✓ Registration successful")
        print(f"   Response: {resp.json()}")
    elif resp.status_code == 409:
        print(f"   ℹ User already exists (this is OK)")
    else:
        print(f"   ✗ Error: {resp.json()}")
except Exception as e:
    print(f"   ✗ Connection error: {e}")

# Test 2: Login
print("\n2. Testing login...")
try:
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": "test@example.com",
            "password": "test1234"
        }
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✓ Login successful")
        print(f"   Token: {data['token'][:50]}...")
        print(f"   User: {data['user']['name']} ({data['user']['email']})")
        
        # Test 3: Use token to access protected endpoint
        print("\n3. Testing protected endpoint...")
        headers = {"Authorization": f"Bearer {data['token']}"}
        resp = requests.get(f"{BASE_URL}/dashboard", headers=headers)
        print(f"   Dashboard Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"   ✓ Dashboard access successful")
        else:
            print(f"   ✗ Dashboard error: {resp.json()}")
    else:
        print(f"   ✗ Login failed: {resp.json()}")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 50)
print("Testing complete!")
