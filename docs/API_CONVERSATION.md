# API Conversazioni - Quick Reference

## 1. Lista Conversazioni (senza storico)

```http
GET /chats/{user_id}
```

**Response:**
```json
{
  "id": 792,
  "user_id": 5,
  "db_id": "primo",
  "title": "Energia consumata",
  "created_at": "2025-12-11T08:30:00",
  "message_count": 2
}
```

---

## 2. Conversazione Specifica (con messaggi)

```http
GET /chats/{chat_id}/messages
```

**Response:**
```json
[
  {
    "id": 19042,
    "role": "user",
    "content": "dimmi quanta energia ho consumato",
    "conversation_id": "b18e66ec-2732-4a6b-a7da-257883115714",
    "created_at": "2025-12-11T08:32:22"
  },
  {
    "id": 19043,
    "role": "bot",
    "content": "Per la commessa...",
    "sql_text": "SELECT...",
    "conversation_id": "b18e66ec-2732-4a6b-a7da-257883115714",
    "created_at": "2025-12-11T08:32:37"
  }
]
```

---

## 3. Correlazione Domanda-Risposta

**Campo:** `conversation_id` (UUID)

- Stesso `conversation_id` = domanda e risposta correlate
- Trova risposta: `WHERE conversation_id = 'xxx' AND role = 'bot'`
- Trova domanda: `WHERE conversation_id = 'xxx' AND role = 'user'`

**Esempio:**
```json
{
  "user_msg": {
    "id": 19042,
    "conversation_id": "b18e66ec-2732-4a6b-a7da-257883115714"
  },
  "bot_msg": {
    "id": 19043,
    "conversation_id": "b18e66ec-2732-4a6b-a7da-257883115714"
  }
}
```

---

## 4. Preferiti con Correlazione

### Aggiungi ai preferiti
```http
POST /favorites
```

**Body:**
```json
{
  "title": "Query energia",
  "question_text": "dimmi quanta energia...",
  "sql_correct": "SELECT...",
  "conversation_id": "b18e66ec-2732-4a6b-a7da-257883115714"
}
```

### Lista preferiti
```http
GET /favorites?user_id={id}
```

**Response:**
```json
[
  {
    "id": 1,
    "title": "Query energia",
    "question_text": "dimmi quanta energia...",
    "sql_correct": "SELECT...",
    "conversation_id": "b18e66ec-2732-4a6b-a7da-257883115714",
    "created_at": "2025-12-11T08:35:00"
  }
]
```

### Aggiorna preferito
```http
PUT /favorites/{favorite_id}
```

**Body:**
```json
{
  "title": "Nuovo titolo",
  "conversation_id": "b18e66ec-2732-4a6b-a7da-257883115714"
}
```

---

## Flow Completo

```
1. User chiede → POST /storage con conversation_id
   ↓
2. Bot risponde → Stesso conversation_id
   ↓
3. User aggiunge preferito → POST /favorites con conversation_id
   ↓
4. Client aggiorna preferito → PUT /favorites/{id} usando conversation_id
```

---
