from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import openai
import os
from dotenv import load_dotenv
import re

router = APIRouter()
load_dotenv()
client = openai.OpenAI()  



class TableData(BaseModel):
    headers: List[str]
    rows: List[Dict[str, Any]]

class ChartSuggestion(BaseModel):
    chart_type: str
    x_axis: str
    y_axis: List[str]
    explanation: str
def json_cleaning(json: str) -> str:
    if isinstance(json, str):
        if json.startswith("```json"):
            json = json[7:]
        if json.endswith("```"):
            json = json[:-3]
        return "\n".join([line for line in json.split("\n") if not line.strip().startswith("--")])
    return ""
@router.post("/generate-chart", response_model=ChartSuggestion)


def generate_chart(data: TableData):
    try:
        prompt = build_prompt(data.headers, data.rows)

        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
    { "role": "system", "content": (
       "You are a strict JSON-only assistant. Return ONLY valid JSON. Do not use markdown, do not include text outside the JSON."
        "Given a table (headers and rows), choose the most suitable chart type, X and Y axis, and explain why. "
        "Return ONLY valid JSON with the following keys: chart_type, x_axis, y_axis, explanation. "
        "DO NOT include any text outside the JSON."
    )},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        result = response.choices[0].message.content

        import json
        try:
            cleaned = json_cleaning(result)

            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            raise HTTPException(500, detail="OpenAI response is not valid JSON:\n" + result)

        return ChartSuggestion(**parsed)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chart generation failed: {e}")


def build_prompt(headers: List[str], rows: List[Dict[str, Any]]) -> str:
    example_data = rows[:10]
    def clean(value):
        if isinstance(value, str):
            value = value.replace("€", "").replace(",", ".").strip()
            try:
                return float(value)
            except ValueError:
                return value
        return value

    example_data = [
        {k: clean(v) for k, v in row.items()}
        for row in rows[:10]
    ]
    print  ("📊 Example data for prompt:", example_data)
    return f"""
Dati tabulari:
Colonne: {headers}
Esempio di righe:
{example_data}

Scegli:
- Tipo di grafico più adatto (bar, line, pie, scatter, ecc)
- Colonna X
- Colonne Y (una o più colonne numeriche) — come lista

Rispondi solo in JSON nel formato seguente:
{{
  "chart_type": "bar",
  "x_axis": "nome_attivita",
  "y_axis": ["ore_consuntivate", "valore_economico"],
  "explanation": "..."
}}
"""

