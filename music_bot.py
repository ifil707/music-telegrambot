import os
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import Optional
import time
import urllib.parse

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import yt_dlp
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB Telegram limit
MAX_DURATION = 600  # 10 minutes max duration
TEMP_DIR = tempfile.gettempdir()

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Тексты сообщений
TEXTS = {
    "welcome": """🎵 **Музыкальный бот с множественными источниками**

**Что я умею:**
• 🔍 Ищу музыку в разных источниках интернета
• 📤 Отправляю треки в высоком качестве MP3
• 🌐 Использую несколько площадок для поиска
• ⚡ Найду даже редкие композиции

**Источники поиска:**
• YouTube (через yt-dlp)
• Zaycev.net (русскоязычная музыка)
• SoundCloud (независимые артисты)
• Free Music Archive (лицензионная музыка)

**Как пользоваться:**
Просто напишите название трека или исполнителя

**Примеры:**
• Imagine Dragons Radioactive
• The Beatles Hey Jude
• Билан Дима Нео
• Miyagi Kosandra

Выберите действие:""",

    "help": """🆘 **Справка по многоисточниковому боту**

**Основные возможности:**
🔍 **Поиск музыки** - напишите название трека или исполнителя

**Источники поиска (по порядку):**
1. 🎥 **YouTube** - самая большая база треков
2. 🎵 **Zaycev.net** - русскоязычная и мировая музыка
3. 🎧 **SoundCloud** - независимые артисты и ремиксы
4. 📻 **Free Music Archive** - лицензионная музыка

**Примеры запросов:**
• "Imagine Dragons Radioactive"
• "Монеточка - Каждый раз"  
• "Eminem Lose Yourself"
• "Miyagi Kosandra"

**Как это работает:**
1. Ищем трек на первом источнике
2. Если не найден - переходим к следующему
3. Как только найден - скачиваем и отправляем

**Преимущества:**
• Высокий процент успешных поисков
• Разнообразие музыкальных стилей
• Обход блокировок отдельных площадок
• Автоматический выбор лучшего качества

**Технические характеристики:**
• Качество: MP3 до 320kbps
• Максимальный размер: 50MB
• Максимальная длительность: 10 минут

**Ограничения:**
• Некоторые треки могут быть недоступны
• Время поиска: 30-60 секунд
• Авторские права соблюдаются

**Команды:**
/start - главное меню
/help - эта справка""",

    "search_prompt": """🔍 **Мультиисточниковый поиск музыки**

Отправьте мне название трека, который хотите найти.

**Примеры запросов:**
• Imagine Dragons Radioactive  
• The Beatles - Hey Jude
• Монеточка Каждый раз
• Drake God's Plan
• Billie Eilish bad guy

**Источники поиска:**
🎥 YouTube → 🎵 Zaycev.net → 🎧 SoundCloud → 📻 FMA

Я найду трек на одной из площадок и отправлю аудиофайл.""",

    "searching_youtube": "🎥 Ищу на **YouTube**: {}",
    "searching_zaycev": "🎵 Ищу на **Zaycev.net**: {}",
    "searching_soundcloud": "🎧 Ищу на **SoundCloud**: {}",
    "searching_fma": "📻 Ищу в **Free Music Archive**: {}",
    "downloading": "📥 Скачиваю с **{}**: {}",
    "sending": "📤 Отправляю: {}",
    "found_on": "✅ Найдено на: **{}**",
    "not_found_anywhere": "❌ Не найден: **{}**\n\n🔍 Поиск выполнен на всех площадках:\n• YouTube\n• Zaycev.net\n• SoundCloud\n• Free Music Archive\n\nПопробуйте:\n• Изменить запрос\n• Добавить имя исполнителя\n• Написать на английском/русском",
    "too_short": "❌ Слишком короткий запрос. Напишите хотя бы 2 символа.",
    "too_long": "❌ Слишком длинный запрос. Максимум 100 символов.",
    "too_long_track": "❌ Трек слишком длинный (больше 10 минут)",
    "too_big_file": "❌ Файл слишком большой (больше 50MB)",
    "error": "❌ Произошла ошибка при поиске. Попробуйте еще раз через минуту.",
}

class MusicStates(StatesGroup):
    waiting_search_query = State()

class MultiSourceDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    async def search_youtube(self, query: str) -> Optional[str]:
        """Поиск на YouTube через yt-dlp"""
        try:
            logger.info(f"YouTube search: {query}")
            output_path = os.path.join(TEMP_DIR, f"yt_{int(time.time())}")

            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': f'{output_path}.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '192',
                'prefer_ffmpeg': True,
                'keepvideo': False,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }

            search_query = f"ytsearch1:{query}"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)

                if not info or not info.get('entries'):
                    return None

                video_info = info['entries'][0]
                duration = video_info.get('duration', 0)

                if duration and duration > MAX_DURATION:
                    return "TOO_LONG"

                ydl.download([video_info['webpage_url']])

                mp3_file = f"{output_path}.mp3"
                if os.path.exists(mp3_file):
                    file_size = os.path.getsize(mp3_file)
                    if file_size <= MAX_FILE_SIZE:
                        return mp3_file
                    else:
                        os.remove(mp3_file)
                        return "TOO_BIG"

                return None

        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            return None

    async def search_zaycev(self, query: str) -> Optional[str]:
        """Поиск на Zaycev.net"""
        try:
            logger.info(f"Zaycev search: {query}")

            # Поиск трека
            search_url = f"https://zaycev.net/search.html?query_search={urllib.parse.quote(query)}"
            response = self.session.get(search_url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Ищем первый трек в результатах
            track_links = soup.select('div.musicset-track a.musicset-track__link')
            if not track_links:
                return None

            track_url = "https://zaycev.net" + track_links[0].get('href')

            # Переходим на страницу трека
            track_response = self.session.get(track_url, timeout=15)
            track_response.raise_for_status()

            track_soup = BeautifulSoup(track_response.text, 'html.parser')

            # Ищем ссылку на скачивание
            download_link = None

            # Вариант 1: прямая ссылка на MP3
            audio_element = track_soup.select_one('audio source')
            if audio_element:
                download_link = audio_element.get('src')

            # Вариант 2: кнопка скачивания
            if not download_link:
                download_btn = track_soup.select_one('a[href*=".mp3"]')
                if download_btn:
                    download_link = download_btn.get('href')

            # Вариант 3: data-url атрибут
            if not download_link:
                data_url = track_soup.select_one('[data-url*=".mp3"]')
                if data_url:
                    download_link = data_url.get('data-url')

            if not download_link:
                return None

            # Нормализуем ссылку
            if download_link.startswith('//'):
                download_link = 'https:' + download_link
            elif download_link.startswith('/'):
                download_link = 'https://zaycev.net' + download_link

            # Скачиваем файл
            output_path = os.path.join(TEMP_DIR, f"zaycev_{int(time.time())}.mp3")

            audio_response = self.session.get(download_link, timeout=30, stream=True)
            audio_response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in audio_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # Проверяем размер файла
            if os.path.getsize(output_path) > MAX_FILE_SIZE:
                os.remove(output_path)
                return "TOO_BIG"

            return output_path

        except Exception as e:
            logger.error(f"Zaycev search error: {e}")
            return None

    async def search_soundcloud(self, query: str) -> Optional[str]:
        """Поиск на SoundCloud через yt-dlp"""
        try:
            logger.info(f"SoundCloud search: {query}")
            output_path = os.path.join(TEMP_DIR, f"sc_{int(time.time())}")

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{output_path}.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '192',
                'prefer_ffmpeg': True,
            }

            # Поиск на SoundCloud
            search_query = f"scsearch1:{query}"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)

                if not info or not info.get('entries'):
                    return None

                track_info = info['entries'][0]
                duration = track_info.get('duration', 0)

                if duration and duration > MAX_DURATION:
                    return "TOO_LONG"

                ydl.download([track_info['webpage_url']])

                mp3_file = f"{output_path}.mp3"
                if os.path.exists(mp3_file):
                    file_size = os.path.getsize(mp3_file)
                    if file_size <= MAX_FILE_SIZE:
                        return mp3_file
                    else:
                        os.remove(mp3_file)
                        return "TOO_BIG"

                return None

        except Exception as e:
            logger.error(f"SoundCloud search error: {e}")
            return None

    async def search_free_music_archive(self, query: str) -> Optional[str]:
        """Поиск в Free Music Archive"""
        try:
            logger.info(f"FMA search: {query}")

            # Поиск через API FMA (упрощенная версия)
            search_url = f"https://freemusicarchive.org/search/?q={urllib.parse.quote(query)}&limit=1"
            response = self.session.get(search_url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Ищем ссылку на трек
            track_link = soup.select_one('a[href*="/music/"]')
            if not track_link:
                return None

            track_url = "https://freemusicarchive.org" + track_link.get('href')

            # Переходим на страницу трека
            track_response = self.session.get(track_url, timeout=15)
            track_response.raise_for_status()

            track_soup = BeautifulSoup(track_response.text, 'html.parser')

            # Ищем прямую ссылку на MP3
            download_link = None

            # Ищем аудио элемент
            audio_element = track_soup.select_one('audio source[src*=".mp3"]')
            if audio_element:
                download_link = audio_element.get('src')

            # Ищем ссылку на скачивание
            if not download_link:
                download_btn = track_soup.select_one('a[href*=".mp3"]')
                if download_btn:
                    download_link = download_btn.get('href')

            if not download_link:
                return None

            # Нормализуем ссылку
            if download_link.startswith('/'):
                download_link = 'https://freemusicarchive.org' + download_link

            # Скачиваем файл
            output_path = os.path.join(TEMP_DIR, f"fma_{int(time.time())}.mp3")

            audio_response = self.session.get(download_link, timeout=30, stream=True)
            audio_response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in audio_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # Проверяем размер файла
            if os.path.getsize(output_path) > MAX_FILE_SIZE:
                os.remove(output_path)
                return "TOO_BIG"

            return output_path

        except Exception as e:
            logger.error(f"FMA search error: {e}")
            return None

    async def download_track(self, query: str, status_callback=None) -> tuple[Optional[str], str]:
        """Основная функция поиска по всем источникам"""
        sources = [
            ("YouTube", self.search_youtube),
            ("Zaycev.net", self.search_zaycev),
            ("SoundCloud", self.search_soundcloud),
            ("Free Music Archive", self.search_free_music_archive)
        ]

        for source_name, search_func in sources:
            try:
                if status_callback:
                    await status_callback(f"searching_{source_name.lower().replace(' ', '_').replace('.', '')}", query)

                result = await search_func(query)

                if result == "TOO_LONG":
                    return "TOO_LONG", source_name
                elif result == "TOO_BIG":
                    return "TOO_BIG", source_name
                elif result and os.path.exists(result):
                    return result, source_name

                # Небольшая пауза между источниками
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error searching {source_name}: {e}")
                continue

        return None, "nowhere"

    def cleanup_file(self, file_path: str):
        """Удаление временного файла"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")

# Инициализация
downloader = MultiSourceDownloader()

# Создание клавиатур
def main_menu():
    """Главное меню бота"""
    keyboard = [
        [InlineKeyboardButton(text="🔍 Поиск музыки", callback_data="search_music")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def back_menu():
    """Кнопка возврата в главное меню"""
    keyboard = [
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Обработчики команд
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    """Команда /start"""
    await msg.answer(TEXTS["welcome"], reply_markup=main_menu(), parse_mode="Markdown")

@dp.message(Command("help"))  
async def help_cmd(msg: Message):
    """Команда /help"""
    await msg.answer(TEXTS["help"], reply_markup=back_menu(), parse_mode="Markdown")

# Обработчики callback-запросов
@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(query: CallbackQuery):
    """Возврат в главное меню"""
    await query.message.edit_text(TEXTS["welcome"], reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "help")
async def help_handler(query: CallbackQuery):
    """Справка"""
    await query.message.edit_text(TEXTS["help"], reply_markup=back_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "search_music")
async def search_music_handler(query: CallbackQuery, state: FSMContext):
    """Начало поиска музыки"""
    await query.message.edit_text(TEXTS["search_prompt"], parse_mode="Markdown")
    await state.set_state(MusicStates.waiting_search_query)

# Основная логика поиска и скачивания
async def process_music_search(message: Message, query: str, is_state: bool = False):
    """Общая функция для обработки поиска музыки"""
    # Валидация запроса
    if len(query) < 2:
        await message.answer(TEXTS["too_short"])
        return

    if len(query) > 100:
        await message.answer(TEXTS["too_long"])
        return

    # Исключаем обычные фразы
    excluded = ['привет', 'hello', 'как дела', 'спасибо', 'пока', 'hi', 'hey', 'добрый день', 'добрый вечер']
    if any(word in query.lower() for word in excluded):
        greeting = "👋 Привет! Напишите название трека для поиска музыки."
        if is_state:
            await message.answer(greeting)
        else:
            await message.answer(greeting, reply_markup=main_menu())
        return

    # Создаем статусное сообщение
    status_msg = await message.answer("🔍 **Начинаю поиск...**", parse_mode="Markdown")

    # Функция для обновления статуса
    async def update_status(status_key: str, track_name: str):
        try:
            if status_key == "searching_youtube":
                text = TEXTS["searching_youtube"].format(track_name)
            elif status_key == "searching_zaycev_net":
                text = TEXTS["searching_zaycev"].format(track_name)
            elif status_key == "searching_soundcloud":
                text = TEXTS["searching_soundcloud"].format(track_name)
            elif status_key == "searching_free_music_archive":
                text = TEXTS["searching_fma"].format(track_name)
            else:
                text = f"🔍 Ищу: **{track_name}**"

            await status_msg.edit_text(text, parse_mode="Markdown")
        except:
            pass

    try:
        # Поиск по всем источникам
        result, source = await downloader.download_track(query, update_status)

        if result == "TOO_LONG":
            await status_msg.edit_text(TEXTS["too_long_track"], parse_mode="Markdown")
        elif result == "TOO_BIG":
            await status_msg.edit_text(TEXTS["too_big_file"], parse_mode="Markdown")
        elif result and os.path.exists(result):
            await status_msg.edit_text(TEXTS["sending"].format(query), parse_mode="Markdown")

            # Отправка аудиофайла
            try:
                with open(result, "rb") as audio_file:
                    caption = f"🎵 {query}\n✅ Найдено на: **{source}**"
                    await message.answer_audio(
                        audio=audio_file,
                        caption=caption,
                        parse_mode="Markdown"
                    )

                downloader.cleanup_file(result)

                # Удаляем статусное сообщение
                try:
                    await status_msg.delete()
                except:
                    pass

                # Показываем меню, если это не из состояния
                if not is_state:
                    await message.answer("✅ **Готово!** Хотите найти еще музыку?", 
                                       reply_markup=main_menu(), parse_mode="Markdown")

            except Exception as e:
                logger.error(f"Error sending audio: {e}")
                await status_msg.edit_text("❌ Ошибка отправки файла", parse_mode="Markdown")
        else:
            await status_msg.edit_text(TEXTS["not_found_anywhere"].format(query), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing search query '{query}': {e}")
        await status_msg.edit_text(TEXTS["error"], parse_mode="Markdown")

# Обработчик поискового состояния
@dp.message(MusicStates.waiting_search_query)
async def process_search_query(msg: Message, state: FSMContext):
    """Обработка поискового запроса в состоянии"""
    query = msg.text.strip()
    await process_music_search(msg, query, is_state=True)

    # Очищаем состояние и показываем меню
    await state.clear()
    await asyncio.sleep(2)
    await msg.answer(TEXTS["welcome"], reply_markup=main_menu(), parse_mode="Markdown")

# Обработчик обычных сообщений (прямой поиск)
@dp.message(F.text & ~F.text.startswith('/'))
async def direct_search_handler(message: Message):
    """Прямой поиск без команд"""
    query = message.text.strip()
    await process_music_search(message, query, is_state=False)

async def main():
    """Запуск бота"""
    try:
        logger.info("🎵 Starting Multi-Source Music Bot...")

        # Проверка обязательных настроек
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN not found in environment variables!")
            return

        # Создание временной директории
        Path(TEMP_DIR).mkdir(exist_ok=True)

        # Проверка FFmpeg
        import shutil
        if not shutil.which('ffmpeg'):
            logger.warning("⚠️ FFmpeg not found! Audio conversion may not work properly.")
        else:
            logger.info("✅ FFmpeg found")

        logger.info("🚀 Bot started successfully!")
        logger.info("🌐 Available sources: YouTube, Zaycev.net, SoundCloud, Free Music Archive")

        await dp.start_polling(bot, skip_updates=True)

    except Exception as e:
        logger.error(f"❌ Bot startup error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
