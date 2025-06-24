# scripts/create_chat.py

import sys
import os
import json
from datetime import datetime
from sqlalchemy.orm import Session

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.database import SessionLocal
from models.chat import Chat
from models.messages import Message
from models.user import User  
from sqlalchemy.exc import NoResultFound


EXAMPLE_MESSAGES = [
    {
        "role": "user",
        "content": "mostrami clienti"
    },
    {
        "role": "assistant",
        "content": {
            "sql": "SELECT id_cliente, nome_cliente, codice_lingua FROM anagrafica_clienti;",
            "explanation": "Ecco l'elenco dei clienti presenti nel database."
        }
    },
    {
        "role": "assistant",
        "content": {
            "result_preview": [
                {"id_cliente": 1, "nome_cliente": "Adler Evo", "codice_lingua": "IT"},
                {"id_cliente": 2, "nome_cliente": "Novellini", "codice_lingua": "IT"},
                {"id_cliente": 3, "nome_cliente": "Linecross", "codice_lingua": "EN"},
                {"id_cliente": 4, "nome_cliente": "McClarin", "codice_lingua": "EN"},
                {"id_cliente": 5, "nome_cliente": "Ravak", "codice_lingua": "EN"},
            ],
            "rows_returned": 162
        }
    },
    {
        "role": "user",
        "content": "mostrami clienti"
    },
    {
        "role": "assistant",
        "content": {
            "sql": "SELECT id_cliente, nome_cliente, codice_lingua FROM anagrafica_clienti;",
            "explanation": "Ecco l'elenco dei clienti presenti nel database."
        }
    },
    {
        "role": "assistant",
        "content": {
            "result_preview": [
                {"id_cliente": 1, "nome_cliente": "Adler Evo", "codice_lingua": "IT"},
                {"id_cliente": 2, "nome_cliente": "Novellini", "codice_lingua": "IT"},
                {"id_cliente": 3, "nome_cliente": "Linecross", "codice_lingua": "EN"},
                {"id_cliente": 4, "nome_cliente": "McClarin", "codice_lingua": "EN"},
                {"id_cliente": 5, "nome_cliente": "Ravak", "codice_lingua": "EN"},
            ],
            "rows_returned": 162
        }
    },
]


def create_chat_with_messages(user_id: int):
    db: Session = SessionLocal()

    try:
        user = db.query(User).filter(User.id == user_id).one()

        chat = Chat(
            user_id=user_id,
            title="Mostrami clienti",
            created_at=datetime.utcnow(),
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)

        for msg in EXAMPLE_MESSAGES:
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                message = Message(
                    chat_id=chat.id,
                    role="user" if role == "user" else "bot",
                    content=content,
                    created_at=datetime.utcnow()
                )
            else:
                message = Message(
                    chat_id=chat.id,
                    role="bot",
                    content=json.dumps(content),
                    output=content,
                    created_at=datetime.utcnow()
                )

            db.add(message)

        db.commit()

    finally:
        db.close()


if __name__ == "__main__":
    create_chat_with_messages(user_id=3)
