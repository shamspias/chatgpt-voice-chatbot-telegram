import os
from dotenv import load_dotenv
import openai
import requests
import json
import redis
import celery

load_dotenv()

openai.api_key = os.getenv("OPEN_AI_KEY")

telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

redis_client = redis.Redis(host='localhost', port=6379, db=0)

app = celery.Celery('telegram_chatbot', broker=os.getenv('CELERY_BROKER_URL'))
celery.conf.update(result_backend=os.getenv('CELERY_RESULT_BACKEND'), task_serializer='json', result_serializer='json',
                   accept_content=['json'])


@app.task
def process_message(chat_id, message):
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=message,
        max_tokens=1024,
        n=1,
        stop=None,
        temperature=0.5,
    ).choices[0].text
    send_message(chat_id, response)


def send_message(chat_id, message):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    requests.post(url, json=data)


def handle_update(update):
    chat_id = update["message"]["chat"]["id"]
    message = update["message"]["text"]

    # Remember the last 10 conversations
    redis_client.lpush(f"conversations:{chat_id}", message)
    redis_client.ltrim(f"conversations:{chat_id}", 0, 9)

    # Schedule the message processing task
    process_message.delay(chat_id, message)


def get_updates():
    url = f"https://api.telegram.org/bot{telegram_bot_token}/getUpdates"
    response = requests.get(url)
    return response.json()["result"]


if __name__ == "__main__":
    updates = get_updates()
    for update in updates:
        handle_update(update)
