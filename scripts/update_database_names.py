"""
Script per aggiornare i nomi dei database nel sistema
Rimuove i messaggi "Imported from allowed_databases" e imposta nomi puliti in italiano
"""

import sys
import os

# Aggiungere il percorso root al PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import SessionLocal
from sqlalchemy import text

def clean_database_name(name: str) -> str:
    """Pulisce il nome del database rimuovendo messaggi di importazione"""
    if " (Imported from" in name or " (imported from" in name or " (Updated by" in name:
        # Estrae solo il nome del database prima del messaggio
        return name.split(" (")[0].strip()
    return name

def update_database_names():
    """Aggiorna tutti i nomi dei database nel sistema"""
    db = SessionLocal()
    try:
        print("🔍 Cerco database da aggiornare...")
        
        # Ottiene tutti i database usando SQL diretto
        result = db.execute(text("SELECT id, name, client_id FROM client_databases"))
        databases = result.fetchall()
        
        updated_count = 0
        
        for database in databases:
            db_id, original_name, client_id = database
            cleaned_name = clean_database_name(original_name)
            
            if original_name != cleaned_name:
                print(f"\n📝 Aggiornamento database ID {db_id}:")
                print(f"   Prima:  '{original_name}'")
                print(f"   Dopo:   '{cleaned_name}'")
                
                db.execute(
                    text("UPDATE client_databases SET name = :name WHERE id = :id"),
                    {"name": cleaned_name, "id": db_id}
                )
                updated_count += 1
        
        if updated_count > 0:
            db.commit()
            print(f"\n✅ Aggiornati {updated_count} database con successo!")
        else:
            print("\n✅ Nessun database da aggiornare. Tutti i nomi sono già puliti!")
            
        # Mostra la lista finale
        print("\n📊 Lista database aggiornata:")
        print("=" * 80)
        
        result = db.execute(text("SELECT id, name, client_id FROM client_databases ORDER BY id"))
        databases = result.fetchall()
        
        for db_item in databases:
            db_id, name, client_id = db_item
            status = "🟢" if " (" not in name else "🔴"
            print(f"{status} ID: {db_id:3d} | Nome: {name:40s} | Client ID: {client_id}")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Errore durante l'aggiornamento: {str(e)}")
        raise
    finally:
        db.close()

def main():
    print("=" * 80)
    print("🇮🇹 AGGIORNAMENTO NOMI DATABASE - PULIZIA MESSAGGI DI IMPORTAZIONE")
    print("=" * 80)
    print()
    
    try:
        update_database_names()
        print("\n" + "=" * 80)
        print("✅ Operazione completata con successo!")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ Errore: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
