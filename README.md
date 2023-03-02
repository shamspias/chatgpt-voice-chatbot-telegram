# ChatGPT Voice Chatbot Telegram

ChatGPT Voice Chatbot Telegram is a Python and Flask-based GitHub repository that allows users to communicate with an AI chatbot using voice-to-text and text-to-voice technologies powered by OpenAI. It uses the GPT-3.5 Turbo model for generating text and ChatML for engineering the prompts.


## Features
- Conversational AI chatbot with voice-to-text and text-to-voice support.
- Utilizes OpenAI's GPT-3.5 Turbo model for generating text.
- Stores the last 10 conversations and provides a /clear command to clear them.
- Uses Celery for task scheduling and asynchronous processing.
- Integration with Telegram for seamless messaging.
- Provides a /start or /help command to display a list of available commands.
- Use of google TTS and speech to text and whisper can choice between them.
- Use lasted GPT cost efficent model name `gpt-3.5-turbo`
- ChatML to more efficent the prompt.
- Genarate image as well
- See old conversation by using `/session`
- Genarate Image from Replicate OpenJourney

## Requirements

- Python 3.6 or higher
- Redis
- OpenAI API Key
- Telegram Bot Token
- ffmpeg




## Deployment

### Installation
- Clone the repository to your local machine.
- Install the required dependencies by running pip install -r requirements.txt.
- Set up your OpenAI API credentials and update the .env file with the appropriate values.
- Run the application with python app.py.

### Install requirements
- Install Python3-venv curl redis-server supervisor and FFMPEG
    ```
    sudo apt install python3-venv curl redis-server supervisor ffmpeg -y
    ```
    
    
## Usage
- Start a conversation with the chatbot by messaging the Telegram bot.
- Speak to the chatbot using voice-to-text or type your message directly.
- The chatbot will respond using text-to-voice or text.
- Use the /clear command to clear the conversation history.

## Contribution

Contributions are welcome! Please see the CONTRIBUTING.md file for more details.
