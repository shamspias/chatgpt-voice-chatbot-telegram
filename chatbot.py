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
def generate_image(prompt, number=1):
    response = openai.Image.create(
        prompt=prompt,
        n=number,
        size="512x512"
    )
    image_url = response['data'][0]['url']
    return image_url


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


@bot.message_handler(commands=['image'])
def handle_image(message):
    prompt = message.text.replace("/image", "").strip()
    number = message.text[6:7]
    try:
        numbers = int(number)
    except Exception as e:
        print(str(e))
        numbers = 1
    task = generate_image.apply_async(args=[prompt, numbers])
    image_url = task.get()
    if image_url is not None:
        bot.send_photo(chat_id=message.chat.id, photo=image_url)
    else:
        bot.reply_to(message, "Could not generate image, try again later.")


conversations = []


@bot.message_handler(func=lambda message: True)
def echo_message(message):
    # conversations.append(message.text)
    # conversations = conversations[-10:]  # Keep only the last 10 items
    task = generate_response.apply_async(args=[message.text])
    response = task.get()
    bot.reply_to(message, response)


if __name__ == "__main__":
    bot.polling()
