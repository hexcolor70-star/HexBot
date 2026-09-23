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
    "Butterfly - Patrick Patrikios.aac",
    "Meditation Impromptu 01 - Kevin MacLeod.aac",
    "Meditation Impromptu 02 - Kevin MacLeod.aac",
    "Meditation Impromptu 03 - Kevin MacLeod.aac",
    "Sydney's Skyline - ALBIS.aac",
    "Clover 3 - Vibe Mountain.aac",
    "Radio Flyer - Nathan Moore.aac",
    "The Palace Gardens - Asher Fulero.aac"
]
DURATION = 300  # 5 минут

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

list_intensity = ["Vivid", "Deep", "Pale", "Radiant", "Dusky", "Silken", "Velvet", "Dim", "Bright", "Gleaming", "Shadowy", "Bold", "Soft", "Rich", "Intense", "Muted", "Neon", "Electric", "Dark", "Light", "Shimmering", "Glowing", "Fading", "Dense", "Clear", "Pure", "Raw", "Subtle", "Sharp", "Smooth", "Hazy", "Vibrant", "Melancholy", "Solar", "Lunar", "Astral", "Cosmic", "Mystic", "Ethereal", "Plasma", "Aether", "Quantum", "Prismatic", "Stellar", "Nebula", "Void", "Apex", "Prime", "Ultra", "Super", "Hyper", "Mega", "Giga", "Tera", "Alpha", "Beta", "Gamma", "Delta", "Omega", "Zeta", "Sigma", "Core", "Nexus"]

list_texture = ["Frosty", "Smoky", "Crystal", "Rustic", "Velvet", "Silky", "Glossy", "Matte", "Rough", "Sleek", "Liquid", "Frozen", "Molten", "Burning", "Opal", "Glassy", "Metallic", "Chrome", "Shadow", "Ghost", "Echo", "Mirage", "Prism", "Shard", "Dust", "Ash", "Silt", "Soil", "Stone", "Iron", "Steel", "Bronze", "Silver", "Gold", "Platinum", "Titanium", "Copper", "Brass", "Lead", "Carbon", "Graphite", "Obsidian", "Amber", "Coral", "Pearl", "Jade", "Ruby", "Sapphire", "Topaz", "Quartz", "Granite", "Marble", "Silk", "Satin", "Linen", "Wool", "Cotton", "Fleece", "Hide", "Scale", "Shell", "Bone", "Spore"]

list_modifier = ["Azure", "Cobalt", "Indigo", "Cyan", "Teal", "Emerald", "Mint", "Jade", "Forest", "Olive", "Lime", "Yellow", "Amber", "Gold", "Orange", "Coral", "Crimson", "Ruby", "Scarlet", "Maroon", "Wine", "Berry", "Plum", "Purple", "Violet", "Amethyst", "Lavender", "Pink", "Rose", "Blush", "Peach", "Salmon", "Copper", "Rust", "Brown", "Chocolate", "Coffee", "Sand", "Beige", "Ivory", "Cream", "Snow", "White", "Silver", "Gray", "Slate", "Charcoal", "Jet", "Black", "Midnight", "Navy", "Royal", "Prussian", "Steel", "Ice", "Glacier", "Arctic", "Boreal", "Stellar", "Void", "Abyss", "Depth", "Horizon"]

list_base = ["Sapphire", "Ruby", "Emerald", "Amethyst", "Topaz", "Obsidian", "Amber", "Jade", "Coral", "Pearl", "Quartz", "Granite", "Marble", "Silver", "Gold", "Platinum", "Titanium", "Copper", "Carbon", "Graphite", "Steel", "Iron", "Bronze", "Brass", "Silk", "Velvet", "Satin", "Linen", "Crystal", "Glass", "Prism", "Mirror", "Shadow", "Light", "Beam", "Ray", "Flare", "Glow", "Spark", "Flame", "Fire", "Ash", "Dust", "Smoke", "Mist", "Fog", "Haze", "Cloud", "Storm", "Rain", "Wave", "Tide", "Abyss", "Void", "Space", "Star", "Planet", "Comet", "Meteor", "Pulsar", "Quasar", "Galaxy", "Nexus", "Core"]

def get_color_name(r, g, b):
    rgb_int = (r << 16) | (g << 8) | b
    idx1 = (rgb_int >> 18) & 0x3F
    idx2 = (rgb_int >> 12) & 0x3F
    idx3 = (rgb_int >> 6) & 0x3F
    idx4 = rgb_int & 0x3F
    return f"{list_intensity[idx1]} {list_texture[idx2]} {list_modifier[idx3]} {list_base[idx4]}"
    


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

    # Считаем RGB и название цвета
    hex_clean = hex_code.lstrip('#')
    r_val = int(hex_clean[0:2], 16)
    g_val = int(hex_clean[2:4], 16)
    b_val = int(hex_clean[4:6], 16)
    color_name = get_color_name(r_val, g_val, b_val)
    
    # 1. Жесткий 2-й слот (4-8 сек) — всегда название цвета с плашкой
    mandatory_block = {
        "text": f"{hex_code} - {color_name}", 
        "box": True, 
        "fontsize": 60
    }
    
    # 2. Пул из 10 вопросов для первого варианта
    questions_pool = [
        {"text": f"Do you like Color {hex_code}?", "box": False, "fontsize": 80},
        {"text": f"Would you use {hex_code} in your design?", "box": False, "fontsize": 80},
        {"text": f"How does {hex_code} make you feel?", "box": False, "fontsize": 80},
        {"text": f"Is {hex_code} your style?", "box": False, "fontsize": 80},
        {"text": f"What do you think of {hex_code}?", "box": False, "fontsize": 80},
        {"text": f"Can you imagine {hex_code} on your wall?", "box": False, "fontsize": 75},
        {"text": f"Does {hex_code} look bright to you?", "box": False, "fontsize": 80},
        {"text": f"Rate this color {hex_code} from 1 to 10!", "box": False, "fontsize": 80},
        {"text": f"Would this shade fit a modern room?", "box": False, "fontsize": 75},
        {"text": f"Have you ever seen a color like {hex_code}?", "box": False, "fontsize": 75}
    ]
    random_question = random.choice(questions_pool)

    # 3. Блок сравнения цвета
    comparison_block = {
        "text": f"Is {hex_code} closer to light or dark?", 
        "box": False, 
        "fontsize": 75
    }

    # 4. Блок подписки
    subscribe_block = {
        "text": "Subscribe and like this video!", 
        "box": False, 
        "fontsize": 80
    }

    # Собираем общую тройку элементов, из которой случайно берем 2 разных для 1-го и 3-го слотов
    three_extras = [random_question, comparison_block, subscribe_block]
    chosen_extras = random.sample(three_extras, k=2)

    # Итоговый порядок: [Слот 1 (0-4с), Слот 2 (4-8с — цвет), Слот 3 (8-12с)]
    chosen_blocks = [
        chosen_extras[0],
        mandatory_block,
        chosen_extras[1]
    ]

    # ЛОГИРУЕМ ПОРЯДОК для проверки в консоли
    block_texts = [b['text'] for b in chosen_blocks]
    logger.info(f"Порядок слотов (0-4с, 4-8с [ЦВЕТ], 8-12с): {block_texts}")

    # Динамически собираем фильтры для 3 слотов по 4 секунды
    intro_filters = []
    prev_label = "0:v"
    
    for i, block in enumerate(chosen_blocks):
        start = i * 4
        end = start + 4
        # 3-й слот (индекс 2) передает метку [v_intro] для таймера
        next_label = f"v_slot{i+1}" if i < 2 else "v_intro"
        
        box_args = ":box=1:boxcolor=black@0.6:boxborderw=20" if block["box"] else ""
        alpha_func = "sin(t/4*PI)" if start == 0 else f"sin((t-{start})/4*PI)"
        
        intro_filters.append(
            f"[{prev_label}]drawtext=fontfile=font.ttf:text='{block['text']}':fontcolor=white:fontsize={block['fontsize']}:"
            f"x=(w-tw)/2:y=(h-th)/2:enable='between(t,{start},{end})':alpha='{alpha_func}'{box_args}[{next_label}]"
        )
        prev_label = next_label

    intro_chain = ";".join(intro_filters)

    cmd = [
        'ffmpeg', '-y', 
        '-f', 'lavfi', '-i', f'color=c={hex_code}:s=1920x1080:d={DURATION}',
        '-i', music,
        '-filter_complex', (
            # 1. Интро по слотам (рандом -> жесткий цвет -> рандом)
            f"{intro_chain};"

            # 2. ТАЙМЕР (сверху справа, прозрачность 0.4)
            f"[v_intro]drawtext=fontfile=font.ttf:text='%{{eif\\:trunc((300-t)/60)\\:d}}\\:%{{eif\\:mod((300-t),60)\\:d\\:2}}':"
            f"x=w-tw-50:y=50:fontsize=60:fontcolor=white@0.4[v1];"

            # 3. Основная плашка HEX и водянка @HexCol
            f"[v1]drawtext=fontfile=font.ttf:text='{hex_code}':x=50:y=h-th-50:fontsize=75:fontcolor=white:box=1:boxcolor=black@0.5[v2];"
            f"[v2]drawtext=fontfile=font.ttf:text='@HexCol':x=w-tw-50:y=h-th-50:fontsize=75:fontcolor=white@0.4[v3];"

            # 4. АУТРО (295-300 сек) - Часть 1
            f"[v3]drawtext=fontfile=font.ttf:text='Thanks for Watching!':fontcolor=white:fontsize=85:"
            f"x=(w-tw)/2:y=(h-th)/2-60:enable='gte(t,295)':alpha='if(lt(t,296),t-295,1)'[v4];"
            
            # 4.1. АУТРО (295-300 сек) - Часть 2
            f"[v4]drawtext=fontfile=font.ttf:text='What do you think of this color\\? Let us know in the comments!':fontcolor=white@0.9:fontsize=48:"
            f"x=(w-tw)/2:y=(h-th)/2+60:enable='gte(t,295)':alpha='if(lt(t,296),t-295,1)'[v4];"

            # 5. Fade In / Fade Out всего видео
            f"[v4]fade=t=in:st=0:d=1,fade=t=out:st={DURATION-1}:d=1[v]"
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
    
    hex_clean = hex_code.lstrip('#')
    r = int(hex_clean[0:2], 16)
    g = int(hex_clean[2:4], 16)
    b = int(hex_clean[4:6], 16)
    color_name = get_color_name(r, g, b)

    # Дальше идет твой старый код загрузки с описанием, где теперь есть color_name...

    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
    c_max, c_min = max(r_n, g_n, b_n), min(r_n, g_n, b_n)
    lum = round(((c_max + c_min) / 2) * 100)

    track_title = os.path.splitext(chosen_track)[0]

    # 2. Динамический пул тегов (генерируем заранее, чтобы использовать и в API, и в описании)
    base_tags = [
        hex_code, 
        f"hex {hex_code}", 
        f"rgb {r} {g} {b}", 
        "hex color", 
        "rgb spectrum", 
        "color reference",
        "color codes", 
        "hex code preview", 
        "color library", 
        "aesthetic colors",
        "color palette", 
        "visual reference", 
        "design colors"
    ]
    chosen_tags = random.sample(base_tags, k=8)

    # Формируем строки для текста описания из выбранных тегов
    keywords_str = ", ".join(chosen_tags)
    # Делаем хэштеги (убираем пробелы из фраз для валидности хэштегов, например #hex00ff00)
    hashtags_str = " ".join([f"#{tag.replace(' ', '')}" for tag in chosen_tags])

    # 3. Описание (3 шаблона) с добавлением ключевых слов и хэштегов в конец
    desc_1 = f"""Color Code: {hex_code}
This is a visual reference for the HEX color {hex_code}. 
This video is part of a massive project to document all 16,777,216 colors in the RGB spectrum.

Technical Details:
- HEX: {hex_code}
- RGB Values: rgb({r}, {g}, {b})
- Luminance: {lum}%
- Music Track: {track_title}
- Project: Visual HEX Color Library
- Color Name (Unique): {color_name}
Licensed under Creative Commons Attribution 4.0:
Source: http://incompetech.com/music/royalty-free/index.html
Music by Kevin MacLeod: http://incompetech.com/music/

Keywords: {keywords_str}

{hashtags_str}"""

    desc_2 = f"""HEX Color Display: {hex_code}

Visual preview of the color shade {hex_code} (RGB: {r}, {g}, {b}).
This upload is part of an archival project covering all 16,777,216 RGB colors.

Specifications:
- Color: {hex_code}
- Red / Green / Blue: {r} / {g} / {b}
- Audio Track: {track_title}
- Archive: Visual HEX Color Library
- Name of Color: {color_name}

Licensed under Creative Commons Attribution 4.0:
Source: http://incompetech.com/music/royalty-free/index.html
Music by Kevin MacLeod: http://incompetech.com/music/

Keywords: {keywords_str}

{hashtags_str}"""

    desc_3 = f"""Visual Reference for {hex_code}

Color Shade: {hex_code}
RGB Spectrum values: rgb({r}, {g}, {b}) | Lightness: {lum}%

This video is part of a massive project to document all 16,777,216 colors in the RGB spectrum.

Audio & Credits:
- Track: {track_title}
- Project: Visual HEX Color Library

- Color: {color_name}

Licensed under Creative Commons Attribution 4.0:
Source: http://incompetech.com/music/royalty-free/index.html
Music by Kevin MacLeod: http://incompetech.com/music/

Keywords: {keywords_str}

{hashtags_str}"""

    description = random.choice([desc_1, desc_2, desc_3])

    # 4. Сборка тела запроса
    body = {
        'snippet': {
            'title': f"What does {hex_code} - {color_name} look like? | Color Code Preview",
            'description': description,
            'tags': chosen_tags
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
  
