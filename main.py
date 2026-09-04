import os
import random
import subprocess
import logging
import re
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

MUSIC_TRACKS = [
    "Classic Rose 2 - Vibe Mountains.aac", 
    "Alternate - Vibe Tracks.aac", 
    "Cipher - Kevin MacLeod.aac", 
    "Nebula - The Grey Room.aac", 
    "Butterfly - Patrick Patrikios.aac"
]
DURATION = 300  # 5 минут

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def get_youtube_client():
    token_data = os.environ.get("G_TOKEN_JSON")
    
    if token_data:
        logger.info("Авторизация через GitHub Secrets...")
        creds = Credentials.from_authorized_user_info(json.loads(token_data), ['https://www.googleapis.com/auth/youtube'])
    elif os.path.exists("token.json"):
        logger.info("Авторизация через локальный файл token.json...")
        creds = Credentials.from_authorized_user_file("token.json", ['https://www.googleapis.com/auth/youtube'])
    else:
        raise FileNotFoundError("Ошибка: Токен не найден ни в Secrets (G_TOKEN_JSON), ни в файле token.json!")

    return build('youtube', 'v3', credentials=creds)


def get_next_index(youtube):
    logger.info("Проверяем последний загруженный цвет на канале...")
    try:
        channel_req = youtube.channels().list(mine=True, part='contentDetails')
        channel_resp = channel_req.execute()
        uploads_playlist_id = channel_resp['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        playlist_req = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part='snippet',
            maxResults=1
        )
        playlist_resp = playlist_req.execute()

        if not playlist_resp.get('items'):
            logger.info("Канал пуст. Начинаем с самого начала (#000000).")
            return 0

        latest_title = playlist_resp['items'][0]['snippet']['title']
        logger.info(f"Найдено последнее видео: '{latest_title}'")

        match = re.search(r'#([0-9A-Fa-f]{6})', latest_title)
        if match:
            last_hex = match.group(1)
            next_index = int(last_hex, 16) + 1
            logger.info(f"Последний цвет был #{last_hex}. Следующий индекс для загрузки: {next_index}")
            return next_index
        else:
            logger.warning("Не удалось найти HEX-код в названии последнего видео! Начинаем с 0.")
            return 0

    except Exception as e:
        logger.error(f"Ошибка при проверке канала: {e}")
        raise RuntimeError("Не удалось получить данные канала. Проверь токен и квоты.")


def create_video(hex_code, music, output):
    logger.info(f"Начинаю генерацию видео для {hex_code} с треком {music}...")
    
    if not os.path.exists(music):
        raise FileNotFoundError(f"Аудиофайл {music} не найден в репозитории!")
        
    if not os.path.exists("font.ttf"):
        raise FileNotFoundError("Шрифт font.ttf не найден в репозитории!")

    cmd = [
        'ffmpeg', '-y', 
        '-f', 'lavfi', '-i', f'color=c={hex_code}:s=1920x1080:d={DURATION}',
        '-i', music,
        '-filter_complex', (
            f"[0:v]drawtext=fontfile=font.ttf:text='{hex_code}':x=50:y=h-th-50:fontsize=75:fontcolor=white:box=1:boxcolor=black@0.5,"
            f"drawtext=fontfile=font.ttf:text='@HexCol':x=w-tw-50:y=h-th-50:fontsize=75:fontcolor=white@0.4,"
            f"fade=t=in:st=0:d=1,fade=t=out:st={DURATION-1}:d=1[v]"
        ),
        '-map', '[v]', 
        '-map', '1:a',
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p', 
        '-c:a', 'copy',
        '-t', str(DURATION), 
        output
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"ОШИБКА FFMPEG:\n{e.stderr}")
        raise

    logger.info(f"Видео {output} успешно создано.")


def upload_video(youtube, video_file, hex_code, chosen_track):
    logger.info("Подготовка к загрузке на YouTube...")

    description = f"""Color Code: {hex_code}
This is a visual reference for the HEX color {hex_code}. 
This video is part of a massive project to document all 16,777,216 colors in the RGB spectrum.

Technical Details:
- HEX: {hex_code}
- Music Track: {os.path.splitext(chosen_track)[0]}
- Project: Visual HEX Color Library

Licensed under Creative Commons Attribution 4.0:
Source: http://incompetech.com/music/royalty-free/index.html
Music by Kevin MacLeod: http://incompetech.com/music/
"""

    body = {
        'snippet': {
            'title': f"What does {hex_code} look like? | Color Code Preview",
            'description': description
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }
    
    logger.info("Отправка файла на серверы YouTube...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(video_file, chunksize=-1, resumable=True)
    )
    response = request.execute()
    logger.info(f"Загрузка завершена! Ссылка на видео: https://youtu.be/{response['id']}")


def main():
    logger.info("Запуск одноразовой итерации бота...")
    video_file = "temp_video.mp4"
    
    try:
        youtube = get_youtube_client()
        current_index = get_next_index(youtube)
        
        if current_index > 16777215:
            logger.info("МИССИЯ ВЫПОЛНЕНА: Все 16 777 216 цветов выложены!")
            return

        hex_code = f"#{current_index:06X}"
        chosen_track = random.choice(MUSIC_TRACKS)
        
        create_video(hex_code, chosen_track, video_file)
        upload_video(youtube, video_file, hex_code, chosen_track)
        
        logger.info("Успешно выложено! Завершаем работу раннера.")

    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
        raise e
    finally:
        if os.path.exists(video_file):
            os.remove(video_file)

if __name__ == "__main__":
    main()
  
