import requests
import os
import aioredis
import json

REDIS_URL = "redis://redis:6379"
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
REALM = "chat_realm"

def get_user_from_keycloak(user_id: str, token: str):
    """ Pobiera użytkownika z Keycloak """
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/{user_id}", headers=headers)
    return response.json() if response.status_code == 200 else None

async def get_user_cached(user_id: str):
    """ Pobiera dane użytkownika z Redis (lub `user_service`, jeśli brak w cache) """
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)

    user_data = await redis.get(f"user:{user_id}")
    if user_data:
        return json.loads(user_data)  # Jeśli mamy cache, zwracamy

    user_data = await get_user_from_keycloak(user_id)  # Pobieramy z `user_service`
    if user_data:
        await redis.set(f"user:{user_id}", json.dumps(user_data), ex=3600)  # Cache na 1h

    return user_data