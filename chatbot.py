import os
import openai
from dotenv import load_dotenv
import telebot
import requests
from gtts import gTTS
from pydub import AudioSegment
from celery import Celery
import speech_recognition as sr

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


def conversation_tracking(text_message, user_id):
    """
    Make remember all the coneversation
    :param user_id: telegram user id
    :param text_message: text message
    :return: str
    """
    # Get the last 10 conversations and responses for this user
    user_conversations = conversations.get(user_id, {'conversations': [], 'responses': []})
    user_messages = user_conversations['conversations'][-9:] + [text_message]
    user_responses = user_conversations['responses'][-9:]

    # Store the updated conversations and responses for this user
    conversations[user_id] = {'conversations': user_messages, 'responses': user_responses}

    # Construct the full conversation history in the "human: bot: " format
    conversation_history = ""
    for i in range(min(len(user_messages), len(user_responses))):
        conversation_history += f"human: {user_messages[i]}\ngenos: {user_responses[i]}\n"

    if conversation_history == "":
        conversation_history = "human:{}\ngenos:".format(text_message)
    else:
        conversation_history += "human:{}\ngenos:".format(text_message)

    # Generate response
    task = generate_response.apply_async(args=[conversation_history])
    response = task.get()

    # Add the response to the user's responses
    user_responses.append(response)

    # Store the updated conversations and responses for this user
    conversations[user_id] = {'conversations': user_messages, 'responses': user_responses}

    return response


@bot.message_handler(commands=["start", "help"])
def start(message):
    if message.text.startswith("/help"):
        bot.reply_to(message, "/code - Helps you to write code, for example: \n/code # Create a python dictionary of 6 "
                              "countries and their capitals\n/clear - Clears old conversations")
    else:
        bot.reply_to(message, "Just start chatting to the AI or enter /help for other commands")


# Define a function to handle voice messages
@bot.message_handler(content_types=["voice"])
def handle_voice(message):
    user_id = message.chat.id
    # Download the voice message file from Telegram servers
    file_info = bot.get_file(message.voice.file_id)
    file = requests.get("https://api.telegram.org/file/bot{0}/{1}".format(
        TELEGRAM_BOT_TOKEN, file_info.file_path))

    print(file_info)

    # Save the file to disk
    with open("voice_message.ogg", "wb") as f:
        f.write(file.content)

    # Use pydub to read in the audio file and convert it to WAV format
    sound = AudioSegment.from_file("voice_message.ogg", format="ogg")
    sound.export("voice_message.wav", format="wav")

    # Use SpeechRecognition to transcribe the voice message
    r = sr.Recognizer()
    with sr.AudioFile("voice_message.wav") as source:
        audio_data = r.record(source)
        text = r.recognize_google(audio_data)

    # Generate response
    replay_text = conversation_tracking(text, user_id)

    # Send the transcribed text back to the user
    bot.reply_to(message, replay_text)

    # Use Google Text-to-Speech to convert the text to speech
    tts = gTTS(replay_text)
    tts.save("voice_message.mp3")

    # Use pydub to convert the MP3 file to the OGG format
    sound = AudioSegment.from_mp3("voice_message.mp3")
    sound.export("voice_message_replay.ogg", format="ogg")

    # Send the transcribed text back to the user as a voice
    voice = open("voice_message_replay.ogg", "rb")
    bot.send_voice(message.chat.id, voice)
    voice.close()

    # Delete the temporary files
    os.remove("voice_message.ogg")
    os.remove("voice_message.wav")
    os.remove("voice_message.mp3")
    os.remove("voice_message_replay.ogg")


@bot.message_handler(commands=["Code", "code"])
def code_handler(message):
    my_text = message.text.lower()
    prompt = my_text.replace("/code", "").strip()
    if prompt == "":
        bot.reply_to(message, "Please enter code or a question after the /code command")
    else:
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

    response = conversation_tracking(message.text, user_id)

    # Reply to message
    bot.reply_to(message, response)


if __name__ == "__main__":
    bot.polling()
