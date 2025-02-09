# app/models.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Alternative(BaseModel):
    option: str  # 'A', 'B', 'C', 'D'
    text: str

class Question(BaseModel):
    question_id: Optional[str] = None  # Será gerado automaticamente se não informado
    text: str
    alternatives: List[Alternative]
    correct_option: Optional[str] = None

class Quiz(BaseModel):
    quiz_id: Optional[str] = None
    title: str
    questions: List[Question] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)