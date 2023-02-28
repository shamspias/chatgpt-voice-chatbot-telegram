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
        prompt="You are an AI named Genos and you are in a conversation with a human. You can answer questions," \
               "provide information, and help with a wide variety of tasks.You are good at writing clean and standard " \
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
    if message.text.startswith("/help"):
        bot.reply_to(message, "/code - Helps you to write code, for example: \n/code # Create a python dictionary of 6 "
                              "countries and their capitals\n/clear - Clears old conversations")
    else:
        bot.reply_to(message, "Just start chatting to the AI or enter /help for other commands")


@bot.message_handler(commands=["Code", "code"])
def code_handler(message):
    my_text = message.text.lower()
    prompt = my_text.replace("/code", "").strip()
    if prompt == "":
        prompt = "# Create a python dictionary of 1 countries and their capitals"
    task = generate_code_response.apply_async(args=[prompt])
    response = task.get()
    bot.reply_to(message, response)


@bot.message_handler(func=lambda message: True)
def echo_message(message):
    user_id = message.chat.id

    # Handle /clear command
    if message.text == '/clear':
        conversations[user_id] = {'conversations': [], 'responses': []}
        bot.reply_to(message, "Conversations and responses cleared!")
        return

    # Get the last 10 conversations and responses for this user
    user_conversations = conversations.get(user_id, {'conversations': [], 'responses': []})
    user_messages = user_conversations['conversations'][-9:] + [message.text]
    user_responses = user_conversations['responses'][-9:]

    # Store the updated conversations and responses for this user
    conversations[user_id] = {'conversations': user_messages, 'responses': user_responses}

    # Construct the full conversation history in the "human: bot: " format
    conversation_history = ""
    for i in range(min(len(user_messages), len(user_responses))):
        conversation_history += f"human: {user_messages[i]}\ngenos: {user_responses[i]}\n"

    if conversation_history == "":
        conversation_history = "human:{}\ngenos:".format(message.text)
    else:
        conversation_history += "human:{}\ngenos:".format(message.text)

    # Generate response
    task = generate_response.apply_async(args=[conversation_history])
    response = task.get()

    # Add the response to the user's responses
    user_responses.append(response)

    # Store the updated conversations and responses for this user
    conversations[user_id] = {'conversations': user_messages, 'responses': user_responses}

    # Reply to message
    bot.reply_to(message, response)


if __name__ == "__main__":
    bot.polling()
