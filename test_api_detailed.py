#!/usr/bin/env python3
"""Test Scope 1 API with detailed debugging."""
import requests
import json
from pprint import pprint

BASE_URL = "http://localhost:8000"

print("=" * 80)
print("DETAILED SCOPE 1 API TEST")
print("=" * 80)

# Test 1: Get transactions
print("\n1. GET /api/escopo1/transactions")
print("-" * 40)
response = requests.get(f"{BASE_URL}/api/escopo1/transactions")
print(f"Status: {response.status_code}")
data = response.json()
print(f"Keys: {list(data.keys())}")

if "erp_transactions" in data:
    print(f"\nERP Transactions ({len(data['erp_transactions'])} total):")
    pprint(data['erp_transactions'][:1])

if "bank_transactions" in data:
    print(f"\nBank Transactions ({len(data['bank_transactions'])} total):")
    pprint(data['bank_transactions'][:1])

# Test 2: Simulate running the reconciliation
print("\n\n2. POST /api/escopo1/run (Execute reconciliation)")
print("-" * 40)
response = requests.post(f"{BASE_URL}/api/escopo1/run")
print(f"Status: {response.status_code}")
result = response.json()
print(f"Result keys: {list(result.keys())}")
pprint(result)

# Test 3: Check decisions after run
print("\n\n3. GET /api/escopo1/decisions (After run)")
print("-" * 40)
response = requests.get(f"{BASE_URL}/api/escopo1/decisions")
print(f"Status: {response.status_code}")
decisions = response.json()
print(f"Decisions keys: {list(decisions.keys())}")
print(f"Number of decisions: {len(decisions.get('decisions', []))}")
if decisions.get('decisions'):
    pprint(decisions['decisions'][0])

# Test 4: Check human queue
print("\n\n4. GET /api/escopo1/human-queue")
print("-" * 40)
response = requests.get(f"{BASE_URL}/api/escopo1/human-queue")
print(f"Status: {response.status_code}")
queue = response.json()
print(f"Queue keys: {list(queue.keys())}")
print(f"Cases in queue: {len(queue.get('cases', []))}")
if queue.get('cases'):
    pprint(queue['cases'][0])

# Test 5: Check quality
print("\n\n5. GET /api/escopo1/quality")
print("-" * 40)
response = requests.get(f"{BASE_URL}/api/escopo1/quality")
print(f"Status: {response.status_code}")
quality = response.json()
pprint(quality)

print("\n" + "=" * 80)
print("If tables are still empty on UI, check browser console for JavaScript errors")
print("=" * 80)
