"""
Test script per verificare i messaggi in italiano nell'API
"""
import requests
import json

BASE_URL = "http://localhost:8001/admin"

# Token (recupera dal tuo sistema)
JWT_TOKEN = "your_jwt_token_here"
ADMIN_TOKEN = "your_admin_token_here"

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "x-admin-token": ADMIN_TOKEN,
    "Content-Type": "application/json"
}

def print_response(title, response):
    """Stampa la risposta in modo leggibile"""
    print(f"\n{'='*80}")
    print(f"📋 {title}")
    print(f"{'='*80}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(response.text)

def test_italian_messages():
    """Test dei messaggi in italiano"""
    
    print("🇮🇹 TEST MESSAGGI API IN ITALIANO")
    print("="*80)
    
    # Test 1: Bulk access creation (successo con skip)
    print("\n1️⃣ Test Creazione Accessi Multipli")
    bulk_data = {
        "user_id": 1,
        "database_ids": [1, 2],  # Usa i tuoi ID
        "can_read": True,
        "can_write": False
    }
    
    response = requests.post(
        f"{BASE_URL}/database-access/bulk",
        headers=headers,
        json=bulk_data
    )
    print_response("Creazione accessi multipli", response)
    
    # Test 2: Try to create duplicate (errore)
    print("\n2️⃣ Test Accesso Duplicato")
    duplicate_data = {
        "user_id": 1,
        "database_id": 1,
        "can_read": True,
        "can_write": False
    }
    
    response = requests.post(
        f"{BASE_URL}/database-access",
        headers=headers,
        json=duplicate_data
    )
    print_response("Tentativo accesso duplicato", response)
    
    # Test 3: Revoke access
    print("\n3️⃣ Test Revoca Accesso")
    # Nota: usa un access_id valido
    access_id = 1
    
    response = requests.delete(
        f"{BASE_URL}/database-access/{access_id}",
        headers=headers
    )
    print_response("Revoca accesso singolo", response)
    
    # Test 4: Revoke all user access
    print("\n4️⃣ Test Revoca Tutti gli Accessi")
    user_id = 1
    
    response = requests.delete(
        f"{BASE_URL}/database-access/user/{user_id}/all",
        headers=headers
    )
    print_response("Revoca tutti gli accessi utente", response)
    
    print("\n" + "="*80)
    print("✅ Test completati!")
    print("="*80)

if __name__ == "__main__":
    print("⚠️  NOTA: Configura i token JWT_TOKEN e ADMIN_TOKEN prima di eseguire!")
    print("⚠️  Puoi usare scripts/get_jwt_token.py e scripts/get_admin_token.py")
    print()
    
    # Decommentare dopo aver configurato i token:
    # test_italian_messages()
    
    print("✅ Script pronto. Configura i token e decommenta la chiamata.")
