import os
import time
import logging
import sys

from dotenv import load_dotenv
import requests
from telebot import TeleBot
from telebot.apihelper import ApiException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, token in tokens.items() if not token]
    if missing_tokens:
        for token in missing_tokens:
            logging.critical(
                f'Отсутствует обязательная переменная окружения: {token}'
            )
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Сообщение в Telegram отправлено: {message}')
    except ApiException as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')
    except requests.RequestException as error:
        logging.error(
            f'Ошибка сети при отправке сообщения в Telegram: {error}'
        )


def get_api_answer(timestamp):
    """Запрос к API-сервису."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        logging.error(f'Ошибка при запросе к API: {error}')
        raise RuntimeError(f'Ошибка при запросе к API: {error}')

    if response.status_code != 200:
        logging.error(
            f'Эндпоинт {ENDPOINT} вернул код {response.status_code}'
        )
        raise RuntimeError(
            f'Эндпоинт {ENDPOINT} вернул код {response.status_code}'
        )

    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        logging.error('Ответ API не является словарем')
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        logging.error('Ключ "homeworks" отсутствует в ответе API')
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')
    if not isinstance(response['homeworks'], list):
        logging.error('Ответ API по ключу "homeworks" не является списком')
        raise TypeError('Ответ API по ключу "homeworks" не является списком')
    return response['homeworks']


def parse_status(homework):
    """Извлечение статуса работы из ответа API."""
    if not isinstance(homework, dict):
        logging.error('Домашняя работа не является словарем')
        raise TypeError('Домашняя работа не является словарем')
    if 'homework_name' not in homework:
        logging.error('Ключ "homework_name" отсутствует в ответе API')
        raise KeyError('Ключ "homework_name" отсутствует в ответе API')
    if 'status' not in homework:
        logging.error('Ключ "status" отсутствует в ответе API')
        raise KeyError('Ключ "status" отсутствует в ответе API')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        logging.error(f'Неизвестный статус домашней работы: {status}')
        raise ValueError(f'Неизвестный статус домашней работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log')
        ]
    )

    if not check_tokens():
        sys.exit('Отсутствуют обязательные переменные окружения')

    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
                    timestamp = response.get('current_date', timestamp)
            else:
                logging.debug('Отсутствие новых статусов в ответе API')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_message:
                try:
                    send_message(bot, message)
                    last_message = message
                except ApiException as send_error:
                    logging.error(
                        f'Ошибка при отправке сообщения в Telegram: {send_error}'
                    )
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
