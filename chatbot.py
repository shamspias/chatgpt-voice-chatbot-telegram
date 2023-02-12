import os

import openai
from dotenv import load_dotenv
import telebot
from celery import Celery

load_dotenv()

openai.api_key = os.getenv('OPEN_AI_KEY')

app = Celery('chatbot', broker=os.getenv('CELERY_BROKER_URL'))

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


@app.task
def generate_response(message_text):
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="You are an AI named Sonic and you are in a conversation with a human. You can answer questions, "
               "provide information, and help with a wide variety of tasks.\n\n" + message_text,
        temperature=0.7,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    ).choices[0].text

    return response.replace("ChatBot: ", "")


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Hello! How can I help you today?")


@bot.message_handler(func=lambda message: True)
def echo_message(message):
    task = generate_response.apply_async(args=[message.text])
    response = task.get()
    bot.reply_to(message, response)


if __name__ == "__main__":
    bot.polling()
