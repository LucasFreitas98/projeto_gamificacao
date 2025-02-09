# app/database.py
import os
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Criando um cliente global com pooling
redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)