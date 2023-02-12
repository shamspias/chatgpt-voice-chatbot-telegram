# Telegram Chatbot with GPT-3 and Celery
This repository contains an example of a Telegram chatbot integrated with OpenAI's GPT-3 and Celery for task queue management. The chatbot can respond to messages, store the last 10 conversations for each user, and efficiently process messages using Celery.

## Requirements

- Python 3.6 or higher
- Redis
- OpenAI API Key
- Telegram Bot Token

## Usage

- Clone the repository:
   ```
  $ git clone https://github.com/[YOUR_GITHUB_USERNAME]/telegram-chatbot-gpt3-celery.git
  ```
- Create a virtual environment and activate it:
    ```
    $ python3 -m venv env
    $ source env/bin/activate
    ```
- Install the dependencies:
    ```
    pip install -r requirements.txt
    ```
- Set the following environment variables:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token
   - `OPENAI_API_KEY`: Your OpenAI API Key
  
- Start the Redis server:
    `redis-server`

- Start the Celery worker:
    ```
    celery -A telegram_chatbot worker --loglevel=info
    ```
- Run the script:
    ```
    python chatbot.py
    ```
- Start a conversation with your Telegram bot!


## Contributing

This is just a starting point and there's always room for improvement. If you have any ideas or suggestions, feel free to open an issue or submit a pull request.

## License
This project is licensed under the MIT License. See the LICENSE file for details.



