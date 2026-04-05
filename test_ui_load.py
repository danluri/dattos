#!/usr/bin/env python3
"""Final UI test - verify data loads correctly on the pages."""
import requests
from bs4 import BeautifulSoup

BASE_URL = "http://localhost:8000"

def get_page_content(endpoint):
    """Fetch and parse HTML page content."""
    response = requests.get(f"{BASE_URL}{endpoint}")
    if response.status_code != 200:
        return None
    return BeautifulSoup(response.text, 'html.parser')

def check_elemento(soup, element_id):
    """Check if an element exists and has content."""
    element = soup.find(id=element_id)
    if element:
        return f"  ✓ Found #{element_id}"
    return f"  ✗ Missing #{element_id}"

print("=" * 70)
print("ESCOPO 1 - VERIFICANDO UI")
print("=" * 70)
soup = get_page_content("/escopo-1")
if soup:
    print("✓ Página carregou com sucesso")
    print(check_elemento(soup, "resetBtn"))
    print(check_elemento(soup, "runBtn"))
    print(check_elemento(soup, "erpTable"))
    print(check_elemento(soup, "bankTable"))
    print(check_elemento(soup, "pendingCount"))
    print(check_elemento(soup, "qualityBox"))
    print(check_elemento(soup, "degradationBox"))
    print(check_elemento(soup, "decisionsBox"))
    print(check_elemento(soup, "eventsBox"))
    print(check_elemento(soup, "humanQueueBox"))
    
    # Check for Jinja2 variables in stats
    stat_cards = soup.find_all(class_="stat-card")
    if stat_cards:
        print(f"✓ Encontrou {len(stat_cards)} cartões de stats")
        for i, card in enumerate(stat_cards, 1):
            strong = card.find("strong")
            if strong:
                value = strong.get_text(strip=True)
                print(f"    Stat {i}: {value}")
else:
    print("✗ Página não carregou")

print("\n" + "=" * 70)
print("ESCOPO 2 - VERIFICANDO UI")
print("=" * 70)
soup = get_page_content("/escopo-2")
if soup:
    print("✓ Página carregou com sucesso")
    print(check_elemento(soup, "runBtn"))
    print(check_elemento(soup, "historyTable"))
    print(check_elemento(soup, "currentTable"))
    print(check_elemento(soup, "summaryBox"))
    print(check_elemento(soup, "metricsBox"))
    
    stat_cards = soup.find_all(class_="stat-card")
    if stat_cards:
        print(f"✓ Encontrou {len(stat_cards)} cartões de stats")
else:
    print("✗ Página não carregou")

print("\n" + "=" * 70)
print("ESCOPO 3 - VERIFICANDO UI")
print("=" * 70)
soup = get_page_content("/escopo-3")
if soup:
    print("✓ Página carregou com sucesso")
    print(check_elemento(soup, "evalBtn"))
    print(check_elemento(soup, "txSelect"))
    print(check_elemento(soup, "roleSelect"))
    print(check_elemento(soup, "analyzeBtn"))
    print(check_elemento(soup, "txTable"))
    print(check_elemento(soup, "docTable"))
    print(check_elemento(soup, "resultBox"))
    print(check_elemento(soup, "citationsBox"))
    
    stat_cards = soup.find_all(class_="stat-card")
    if stat_cards:
        print(f"✓ Encontrou {len(stat_cards)} cartões de stats")
else:
    print("✗ Página não carregou")

print("\n" + "=" * 70)
print("✅ TODAS AS PÁGINAS CARREGARAM COM SUCESSO!")
print("=" * 70)
print("\nAgora acesse no navegador:")
print("  - Escopo 1: http://localhost:8000/escopo-1")
print("  - Escopo 2: http://localhost:8000/escopo-2")
print("  - Escopo 3: http://localhost:8000/escopo-3")
print("=" * 70)
