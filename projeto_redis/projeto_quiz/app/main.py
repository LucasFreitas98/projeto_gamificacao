# app/main.py
import uuid
import json
from datetime import timedelta
from fastapi import FastAPI, HTTPException
from app.models import Quiz, Question, Alternative
from app.database import redis_client
from pydantic import BaseModel

app = FastAPI()

# Tempo de expiração para 30 dias (em segundos)
TTL_30_DAYS = 30 * 24 * 3600

# -----------------------------------------------------------------------------
# Endpoint para criar um Quiz
@app.post("/quiz", response_model=Quiz)
async def create_quiz(quiz: Quiz):
    if not quiz.quiz_id:
        quiz.quiz_id = str(uuid.uuid4())
    key = f"quiz:{quiz.quiz_id}"
    await redis_client.set(key, quiz.json(), ex=TTL_30_DAYS)
    return quiz

# -----------------------------------------------------------------------------
# Endpoint para adicionar uma questão ao quiz
@app.post("/quiz/{quiz_id}/question", response_model=Question)
async def add_question(quiz_id: str, question: Question):
    key = f"quiz:{quiz_id}"
    quiz_data = await redis_client.get(key)
    if not quiz_data:
        raise HTTPException(status_code=404, detail="Quiz not found")
    quiz = Quiz.parse_raw(quiz_data)
    if not question.question_id:
        question.question_id = str(uuid.uuid4())
    quiz.questions.append(question)
    await redis_client.set(key, quiz.json(), ex=TTL_30_DAYS)
    
    # Inicializa contagem de votos para a questão (usando um hash)
    vote_key = f"quiz:{quiz_id}:question:{question.question_id}:votes"
    initial_votes = {"A": 0, "B": 0, "C": 0, "D": 0}
    await redis_client.hset(vote_key, mapping=initial_votes)
    await redis_client.expire(vote_key, TTL_30_DAYS)
    
    # Cria um set para controlar alunos que já votaram
    voted_set_key = f"quiz:{quiz_id}:question:{question.question_id}:voted"
    # Apenas garante que a chave exista e recebe TTL
    await redis_client.delete(voted_set_key)
    await redis_client.expire(voted_set_key, TTL_30_DAYS)
    
    return question

# -----------------------------------------------------------------------------
# Modelo para o voto
class VoteInput(BaseModel):
    student_id: str
    option: str  # Deve ser 'A', 'B', 'C' ou 'D'
    response_time: float  # Tempo em segundos

# Endpoint para registrar voto em uma questão
@app.post("/quiz/{quiz_id}/question/{question_id}/vote")
async def vote(quiz_id: str, question_id: str, vote: VoteInput):
    voted_set_key = f"quiz:{quiz_id}:question:{question_id}:voted"
    # Verifica se o aluno já votou
    if await redis_client.sismember(voted_set_key, vote.student_id):
        raise HTTPException(status_code=400, detail="Student already voted for this question")
    
    # Incrementa o contador de votos
    vote_key = f"quiz:{quiz_id}:question:{question_id}:votes"
    if vote.option not in ["A", "B", "C", "D"]:
        raise HTTPException(status_code=400, detail="Invalid option")
    await redis_client.hincrby(vote_key, vote.option, 1)
    
    # Marca que o aluno votou
    await redis_client.sadd(voted_set_key, vote.student_id)
    
    # Armazena o tempo de resposta em um sorted set para ranking (quanto menor, melhor)
    response_time_key = f"quiz:{quiz_id}:question:{question_id}:response_times"
    await redis_client.zadd(response_time_key, {vote.student_id: vote.response_time})
    await redis_client.expire(response_time_key, TTL_30_DAYS)
    
    return {"message": "Vote recorded"}

# -----------------------------------------------------------------------------
# Endpoint para obter resultados de um quiz (contagem de votos por questão)
@app.get("/quiz/{quiz_id}/results")
async def get_results(quiz_id: str):
    key = f"quiz:{quiz_id}"
    quiz_data = await redis_client.get(key)
    if not quiz_data:
        raise HTTPException(status_code=404, detail="Quiz not found")
    quiz = Quiz.parse_raw(quiz_data)
    
    results = {}
    for question in quiz.questions:
        vote_key = f"quiz:{quiz_id}:question:{question.question_id}:votes"
        vote_counts = await redis_client.hgetall(vote_key)
        results[question.question_id] = vote_counts
    return {"quiz_id": quiz_id, "results": results}

# -----------------------------------------------------------------------------
# Endpoint para obter ranking dos alunos por tempo de resposta em uma questão
@app.get("/quiz/{quiz_id}/question/{question_id}/ranking")
async def get_question_ranking(quiz_id: str, question_id: str):
    response_time_key = f"quiz:{quiz_id}:question:{question_id}:response_times"
    # Ordena do menor para o maior tempo (alunos mais rápidos primeiro)
    ranking = await redis_client.zrange(response_time_key, 0, -1, withscores=True)
    return {"ranking": ranking}