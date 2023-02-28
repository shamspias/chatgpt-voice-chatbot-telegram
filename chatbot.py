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

# Store the last 10 conversations for each user
conversations = {}


@app.task
def generate_image(prompt, number=1):
    response = openai.Image.create(
        prompt=prompt,
        n=number,
        size="512x512"
    )
    image_url = response['data']
    return image_url


@app.task
def generate_code_response(message_text):
    response = openai.Completion.create(
        model="code-davinci-002",
        prompt=message_text,
        temperature=0,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    return response["choices"][0]["text"].strip()


@app.task
def generate_response(message_text):
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="You are an AI named Genos and you are in a conversation with a human. You can answer questions, "
               "provide information, and help with a wide variety of tasks.You are good at writing clean and standard "
               "code.\n\n" + message_text,
        temperature=0.7,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    return response["choices"][0]["text"].strip()


@bot.message_handler(commands=["start", "help"])
def start(message):
    bot.reply_to(message,
                 "Welcome, what would you like to do?\n1.Chat or\n2.Write some code")


@bot.message_handler(commands=["Code", "code"])
def code_handler(message):
    task = generate_code_response.apply_async(args=[message.text])
    response = task.get()
    bot.reply_to(message, response)


@bot.message_handler(func=lambda message: True)
def echo_message(message):
    user_id = message.chat.id

    # Handle /clear command
    if message.text == '/clear':
        conversations[user_id] = []
        bot.reply_to(message, "Conversations cleared!")
        return

    # Get the last 10 conversations for this user
    user_conversations = conversations.get(user_id, [])[-10:]

    # Add the current message to the user's conversations
    user_conversations.append(message.text)

    # Store the updated conversations for this user
    conversations[user_id] = user_conversations
    task = generate_response.apply_async(args=[conversations[user_id]])
    response = task.get()
    bot.reply_to(message, response)


if __name__ == "__main__":
    bot.polling()
