#!/usr/bin/env python3
"""Test all Scope endpoints to validate fixes."""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(method, endpoint, data=None):
    """Test an endpoint and print results."""
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
        else:
            response = requests.post(f"{BASE_URL}{endpoint}", json=data, timeout=5)
        
        print(f"✓ {method} {endpoint}")
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, dict):
                keys = list(result.keys())
                print(f"  Keys: {keys}")
                # Count items in lists
                for key in keys:
                    if isinstance(result[key], list):
                        print(f"    {key}: {len(result[key])} items")
        return True
    except Exception as e:
        print(f"✗ {method} {endpoint}: {e}")
        return False

print("=" * 60)
print("TESTING ESCOPO 1")
print("=" * 60)
test_endpoint("GET", "/escopo-1")
test_endpoint("GET", "/api/escopo1/transactions")
test_endpoint("POST", "/api/escopo1/run")
test_endpoint("GET", "/api/escopo1/decisions")

print("\n" + "=" * 60)
print("TESTING ESCOPO 2")
print("=" * 60)
test_endpoint("GET", "/escopo-2")
test_endpoint("GET", "/api/escopo2/dataset")
test_endpoint("GET", "/api/escopo2/transactions")

print("\n" + "=" * 60)
print("TESTING ESCOPO 3")
print("=" * 60)
test_endpoint("GET", "/escopo-3")
test_endpoint("GET", "/api/escopo3/dataset")
test_endpoint("POST", "/api/escopo3/analyze", {"transaction_id": "TX-1001", "role": "controller"})
test_endpoint("GET", "/api/escopo3/eval")
test_endpoint("POST", "/api/escopo3/search", {"query": "CloudNow", "role": "controller"})

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
