#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000"

endpoints = [
    "/api/escopo1/transactions",
    "/api/escopo1/quality",
    "/api/escopo1/degradation",
    "/api/escopo1/decisions",
    "/api/escopo1/events",
    "/api/escopo1/human-queue",
]

print("Testing Scope 1 API endpoints...\n")

for endpoint in endpoints:
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
        print(f"✓ {endpoint}")
        print(f"  Status: {response.status_code}")
        data = response.json()
        print(f"  Keys: {list(data.keys())}")
        
        # Print sample data
        if endpoint == "/api/escopo1/transactions":
            if "erp_transactions" in data:
                print(f"  ERP transactions count: {len(data['erp_transactions'])}")
                if data['erp_transactions']:
                    print(f"    First: {data['erp_transactions'][0]}")
            if "bank_transactions" in data:
                print(f"  Bank transactions count: {len(data['bank_transactions'])}")
        else:
            print(f"  Data: {json.dumps(data, indent=2)[:300]}")
        print()
    except Exception as e:
        print(f"✗ {endpoint}: {e}\n")
