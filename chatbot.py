import os
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO

import openai
from dotenv import load_dotenv
import telebot
from celery import Celery
import replicate

load_dotenv()

openai.api_key = os.getenv('OPEN_AI_KEY')

app = Celery('chatbot', broker=os.getenv('CELERY_BROKER_URL'))

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

model = replicate.models.get("prompthero/openjourney")
version = model.versions.get("9936c2001faa2194a261c01381f90e65261879985476014a0a37a334593a05eb")


def image_watermark(img_response):
    """
    :param img_response: image url
    :return: Byte image
    """
    img = Image.open(BytesIO(img_response.content))

    # Add the watermark to the image
    draw = ImageDraw.Draw(img)
    watermark_text = "gpt3bots.com"
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
    # Applying text on image via draw object
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
        'prompt': "mdjrny-v4 style" + prompt + "4k resolution",

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
        size="1024x1024"
    )
    image_url = response['data']
    return image_url


@app.task
def generate_response(message_text):
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="You are an AI named Chat Buddy and you are in a conversation with a human. You can answer questions, "
               "provide information, and help with a wide variety of tasks.\n\n" + message_text,
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
                 "Ask anything to the Chat Buddy\n1./ask or just write any question in chat\n2. Use /create (number) "
                 "to generate image\nexample: /create 2 dance with cat\n3. /image to generate image")


@bot.message_handler(commands=["create", "image"])
def handle_image(message):
    space_markup = '                                                                                  '
    image_footer = '[Website](https://gpt3bots.com)'
    caption = f"Powered by **[Chat Buddy](https://t.me/Chatbuddyofficialbot)" + space_markup + image_footer

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
