from fastapi import APIRouter
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
load_dotenv()
router = APIRouter()

class TitleRequest(BaseModel):
    text: str

class TitleResponse(BaseModel):
    title: str

class ChatTitleUpdate(BaseModel):
    chat_id: str
    title: str
@router.post("/api/generate-title", response_model=TitleResponse)
async def generate_title(req: TitleRequest):
    user_text = req.text.strip()
    prompt = (
        "Sei PANDORA AI, un assistente SQL. Genera un titolo breve (max 4 parole) per questa chat: "
        "Il titolo deve riassumere chiaramente la richiesta dell'utente e deve essere facile da leggere in una lista di chat. "
        "Non scrivere spiegazioni, né virgolette, né altro testo. Solo il titolo.\n\n"
        "Testo utente:\n"
        f"{user_text}"
    )

    client = openai.OpenAI()  

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Sei un assistente che crea brevi titoli basati sul primo messaggio dell'utente per la cronologia della chat."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=20,
        temperature=0.6,
        n=1,
    )
    title = response.choices[0].message.content.strip()
    return {"title": title}
