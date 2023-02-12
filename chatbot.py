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


@app.task
def process_message(chat_id, message):
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="You are an AI named Sonic and you are in a conversation with a human. You can answer questions, "
               "provide information, and help with a wide variety of tasks.\n\n" + message,
        temperature=0.7,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
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
