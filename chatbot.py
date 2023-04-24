import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import replicate
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

model = replicate.models.get("prompthero/openjourney")
version = model.versions.get("9936c2001faa2194a261c01381f90e65261879985476014a0a37a334593a05eb")

SYSTEM_PROMPT = os.getenv('SYSTEM_PROMPT')

# Store the last 10 conversations for each user
conversations = {}


def image_watermark(img_response):
    """
    :param img_response: image url
    :return: Byte image
    """
    img = Image.open(BytesIO(img_response.content))

    # Add the watermark to the image
    draw = ImageDraw.Draw(img)
    watermark_text = "DeadlyAI"
    font = ImageFont.truetype("anime.ttf", 20)
    # text_size = draw.textsize(watermark_text, font=font)
    # Positioning Text
    x = 6
    y = 6
    # Add a shadow border to the text
    for offset in range(1, 2):
        draw.text((x - offset, y), watermark_text, font=font, fill=(88, 88, 88))
        draw.text((x + offset, y), watermark_text, font=font, fill=(88, 88, 88))
        draw.text((x, y + offset), watermark_text, font=font, fill=(88, 88, 88))
        draw.text((x, y - offset), watermark_text, font=font, fill=(88, 88, 88))
    # Applying text on image sonic draw object
    draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255))

    # Upload the watermarked image to OpenAI and get the URL
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes = img_bytes.getvalue()
    return img_bytes


@app.task
def generate_image_replicate(prompt):
    inputs = {
        # Input prompt
        'prompt': "mdjrny-v4 style " + prompt + " 4k resolution",

        # Width of output image. Maximum size is 1024x768 or 768x1024 because
        # of memory limits
        'width': 512,

        # Height of output image. Maximum size is 1024x768 or 768x1024 because
        # of memory limits
        'height': 512,

        # Number of images to output
        'num_outputs': 1,

        # Number of denoising steps
        # Range: 1 to 500
        'num_inference_steps': 50,

        # Scale for classifier-free guidance
        # Range: 1 to 20
        'guidance_scale': 6,

        # Random seed. Leave blank to randomize the seed
        # 'seed': ...,
    }
    output = version.predict(**inputs)
    return output[0]


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
def generate_response_chat(message_list):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
                     {"role": "system",
                      "content": SYSTEM_PROMPT},
                 ] + message_list
    )

    return response["choices"][0]["message"]["content"].strip()


@app.task
def generate_response(message_text):
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="You are an AI named sonic and you are in a conversation with a human. You can answer questions, "
               "provide information, and help with a wide variety of tasks.\n\n" + message_text,
        temperature=0.7,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    return response["choices"][0]["text"].strip()


def conversation_tracking(text_message, user_id, old_model=True):
    """
    Make remember all the conversation
    :param old_model: Open AI model
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

    if old_model:
        # Construct the full conversation history in the "human: bot: " format
        conversation_history = ""
        for i in range(min(len(user_messages), len(user_responses))):
            conversation_history += f"human: {user_messages[i]}\nsonic: {user_responses[i]}\n"

        if conversation_history == "":
            conversation_history = "human:{}\nsonic:".format(text_message)
        else:
            conversation_history += "human:{}\nsonic:".format(text_message)

        # Generate response
        task = generate_response.apply_async(args=[conversation_history])
        response = task.get()
    else:
        # Construct the full conversation history in the user:assistant, " format
        conversation_history = []

        for i in range(min(len(user_messages), len(user_responses))):
            conversation_history.append({
                "role": "user", "content": user_messages[i]
            })
            conversation_history.append({
                "role": "assistant", "content": user_responses[i]
            })

        # Add last prompt
        conversation_history.append({
            "role": "user", "content": text_message
        })
        # Generate response
        task = generate_response_chat.apply_async(args=[conversation_history])
        response = task.get()

    # Add the response to the user's responses
    user_responses.append(response)

    # Store the updated conversations and responses for this user
    conversations[user_id] = {'conversations': user_messages, 'responses': user_responses}

    return response


@bot.message_handler(commands=["start", "help"])
def start(message):
    if message.text.startswith("/help"):
        bot.reply_to(message, "/image to generate image animation\n/create generate image\n/clear - Clears old "
                              "conversations\nsend text to get replay\nsend voice to do voice"
                              "conversation")
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
    replay_text = conversation_tracking(text, user_id, True)

    # Send the question text back to the user
    # Send the transcribed text back to the user
    new_replay_text = "Human: " + text + "\n\n" + "sonic: " + replay_text

    bot.reply_to(message, new_replay_text)

    # Use Google Text-to-Speech to convert the text to speech
    tts = gTTS(replay_text)
    tts.save("voice_message.mp3")

    # Use pydub to convert the MP3 file to the OGG format
    sound = AudioSegment.from_mp3("voice_message.mp3")
    sound.export("voice_message_replay.ogg", format="mp3")

    # Send the transcribed text back to the user as a voice
    voice = open("voice_message_replay.ogg", "rb")
    bot.send_voice(message.chat.id, voice)
    voice.close()

    # Delete the temporary files
    os.remove("voice_message.ogg")
    os.remove("voice_message.wav")
    os.remove("voice_message.mp3")
    os.remove("voice_message_replay.ogg")


@bot.message_handler(commands=["create", "image"])
def handle_image(message):
    space_markup = '                                                                                  '
    image_footer = '[Website](https://deadlyai.com)'
    caption = f"Powered by **[Sonic](https://t.me/sonicsaheb)" + space_markup + image_footer

    if message.text.startswith("/image"):
        prompt = message.text.replace("/image", "").strip()
        task = generate_image_replicate.apply_async(args=[prompt])
        image_url = task.get()

        if image_url is not None:
            img_response = requests.get(image_url)
            img_bytes = image_watermark(img_response)

            bot.send_photo(chat_id=message.chat.id, photo=img_bytes, reply_to_message_id=message.message_id,
                           caption=caption, parse_mode='Markdown')
        else:
            bot.reply_to(message, "Could not generate image, try again later.")
    else:
        number = message.text[7:10]
        prompt = message.text.replace("/create", "").strip()
        try:
            numbers = int(number)
        except Exception as e:
            print(str(e))
            numbers = 1
        task = generate_image.apply_async(args=[prompt, numbers])
        image_url = task.get()
        for img in image_url:
            if img['url'] is not None:
                bot.send_photo(chat_id=message.chat.id, photo=img['url'], reply_to_message_id=message.message_id,
                               caption=caption, parse_mode='Markdown')
            else:
                bot.reply_to(message, "Could not generate image, try again later.")


@bot.message_handler(func=lambda message: True)
def echo_message(message):
    user_id = message.chat.id

    # Handle /clear command
    if message.text == '/clear':
        conversations[user_id] = {'conversations': [], 'responses': []}
        bot.reply_to(message, "Conversations and responses cleared!")
        return

    response = conversation_tracking(message.text, user_id, False)

    # Reply to message
    bot.reply_to(message, response)


if __name__ == "__main__":
    bot.polling()
