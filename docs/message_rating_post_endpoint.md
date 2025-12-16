# POST api.pandora-ai.it/auth/message_rating/

**Description:**  
Creates or updates a rating for a message.

## Request body (JSON)
- `message_id` (int) — ID of the message to be rated.
- `rating` (int/float) — The rating value (e.g., 0 or 1).
- `user_id` (int) — ID of the user submitting the rating.

**Example request:**
```json
{
  "message_id": 123,
  "rating": 4,
  "user_id": 456
}
```

## Response
- 200 OK — Rating successfully created or updated.
- 400 Bad Request — Validation error.
- 404 Not Found — Message not found.

**Example response:**
```json
{
  "message_id": 123,
  "rating": 4,
  "user_id": 456,
  "status": "success"
}
```
