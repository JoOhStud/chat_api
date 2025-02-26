from elasticsearch import AsyncElasticsearch
import os

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")

es_client = AsyncElasticsearch([ELASTICSEARCH_URL])

async def index_user(user_id: str, username: str):
    """Indeksuje użytkownika w Elasticsearch"""
    await es_client.index(index="users", id=user_id, body={"id": user_id, "username": username})

async def search_users(query: str):
    """Wyszukuje użytkowników w Elasticsearch"""
    response = await es_client.search(index="users", body={
        "query": {
            "prefix": {"username": query},
        }
    })
    return [hit["_source"] for hit in response["hits"]["hits"]]
  
async def index_message(chat_id: str, sender: str, content: str):
    """Indeksuje wiadomość czatu w Elasticsearch"""
    await es_client.index(index="messages", body={
        "chat_id": chat_id,
        "sender": sender,
        "content": content
    })

async def search_messages(query: str, chat_id: str):
    """Wyszukuje wiadomości w czacie"""
    response = await es_client.search(index="messages", body={
        "query": {
            "bool": {
                "must": [
                    {"match": {"content": query}},
                    {"match": {"chat_id": chat_id}}
                ]
            }
        }
    })
    return [hit["_source"] for hit in response["hits"]["hits"]]