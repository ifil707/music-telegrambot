import os
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import yt_dlp
import vk_api
from vk_api.audio import VkAudio
import yandex_music
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
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN", "")
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB Telegram limit
MAX_DURATION = 600  # 10 minutes max duration
TEMP_DIR = tempfile.gettempdir()

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Тексты сообщений
TEXTS = {
    "welcome": """🎵 **Добро пожаловать в музыкального бота!**

**Что я умею:**
• 🔍 Ищу и скачиваю музыку из интернета
• 📱 Работаю с плейлистами ВКонтакте  
• 🎵 Работаю с плейлистами Яндекс.Музыки
• 📤 Отправляю треки в высоком качестве

**Как пользоваться:**
1. Просто напишите название трека
2. Или выберите плейлист из меню ниже

Выберите действие:""",

    "help": """🆘 **Справка по боту**

**Основные возможности:**
🔍 **Поиск музыки** - напишите название трека
📂 **Плейлисты ВК** - ваши плейлисты из ВКонтакте
📂 **Плейлисты Яндекс** - ваши плейлисты из Яндекс.Музыки

**Примеры запросов:**
• "Imagine Dragons Radioactive"
• "The Beatles Hey Jude"  
• "Eminem Lose Yourself"

**Как работает:**
1. Вы пишете название трека или выбираете плейлист
2. Бот ищет музыку в открытых источниках интернета
3. Скачивает и отправляет вам аудиофайл

**Технические характеристики:**
• Качество: MP3 192kbps
• Максимальный размер: 50MB
• Максимальная длительность: 10 минут
• Источники: YouTube, открытые музыкальные архивы

**Важно:** Бот НЕ копирует файлы из ВК/Яндекс, а ищет треки по названиям в открытых источниках интернета.

**Команды:**
/start - главное меню
/help - эта справка""",

    "search_prompt": """🔍 **Поиск музыки**

Отправьте мне название трека, который хотите найти.

**Примеры:**
• Imagine Dragons Radioactive  
• The Beatles - Hey Jude
• Drake God's Plan
• Billie Eilish bad guy

Я найду трек в открытых источниках интернета и отправлю вам аудиофайл.""",

    "searching": "🔍 Ищу: **{}**\n\n⏳ Поиск в открытых источниках...",
    "downloading": "📥 Скачиваю: **{}**\n\n⏳ Обработка аудио...",
    "sending": "📤 Отправляю: **{}**",
    "not_found": "❌ Не найден: **{}**\n\nПопробуйте изменить запрос или написать по-другому.",
    "too_short": "❌ Слишком короткий запрос. Напишите хотя бы 2 символа.",
    "too_long": "❌ Слишком длинный запрос. Максимум 100 символов.",
    "error": "❌ Произошла ошибка при поиске. Попробуйте еще раз.",

    "vk_loading_playlists": "🔄 Загружаю ваши плейлисты из ВКонтакте...",
    "vk_no_playlists": "❌ Не удалось получить плейлисты из ВК.\n\nВозможные причины:\n• Неверный VK_ACCESS_TOKEN\n• Нет доступа к аудио",
    "vk_playlists_title": "📂 **Ваши плейлисты ВКонтакте** ({} шт.)\n\nВыберите плейлист для скачивания:",
    "vk_loading_tracks": "🔄 Загружаю треки из плейлиста: **{}**",
    "vk_no_tracks": "❌ Не удалось получить треки из плейлиста",
    "vk_tracks_title": "🎵 **Плейлист: {}** ({} треков)\n\nВыберите трек или нажмите 'Скачать все':",

    "yandex_loading_playlists": "🔄 Загружаю ваши плейлисты из Яндекс.Музыки...",
    "yandex_no_playlists": "❌ Не удалось получить плейлисты из Яндекс.Музыки.\n\nВозможные причины:\n• Неверный YANDEX_TOKEN\n• Токен истек",
    "yandex_playlists_title": "📂 **Ваши плейлисты Яндекс.Музыки** ({} шт.)\n\nВыберите плейлист для скачивания:",
    "yandex_loading_tracks": "🔄 Загружаю треки из плейлиста: **{}**",
    "yandex_no_tracks": "❌ Не удалось получить треки из плейлиста",
    "yandex_tracks_title": "🎵 **Плейлист: {}** ({} треков)\n\nВыберите трек или нажмите 'Скачать все':",

    "downloading_playlist": "📥 **Скачиваю плейлист: {}**\n\n⏳ Обрабатываю {} треков...\nЭто может занять несколько минут.",
    "playlist_progress": "📥 **Прогресс: {}/{}**\n\n🎵 Скачиваю: {}",
    "playlist_completed": "✅ **Плейлист скачан!**\n\n📊 Результат:\n• Найдено и отправлено: {} треков\n• Не найдено: {} треков",

    "service_not_configured": "❌ Сервис {} не настроен\n\nОбратитесь к администратору бота для настройки токенов.",
}

class MusicStates(StatesGroup):
    waiting_search_query = State()
    browsing_vk_playlists = State()
    browsing_vk_tracks = State()
    browsing_yandex_playlists = State()
    browsing_yandex_tracks = State()
    downloading_playlist = State()

class TechnicalMusicService:
    def __init__(self):
        self.vk_session = None
        self.vk_audio = None
        self.yandex_client = None
        self.init_services()

    def init_services(self):
        """Инициализация сервисов при запуске"""
        if VK_ACCESS_TOKEN:
            try:
                session = vk_api.VkApi(token=VK_ACCESS_TOKEN)
                self.vk_audio = VkAudio(session)
                self.vk_session = session
                logger.info("✅ VK service initialized")
            except Exception as e:
                logger.error(f"❌ VK init error: {e}")

        if YANDEX_TOKEN:
            try:
                self.yandex_client = yandex_music.Client(YANDEX_TOKEN).init()
                logger.info("✅ Yandex Music service initialized")
            except Exception as e:
                logger.error(f"❌ Yandex init error: {e}")

    async def get_vk_playlists(self) -> List[Dict]:
        """Получение плейлистов из ВК"""
        if not self.vk_session:
            return []
        try:
            vk = self.vk_session.get_api()
            response = vk.audio.getPlaylists(owner_id=None)
            playlists = response.get('items', [])
            return [{"id": pl['id'], "title": pl['title'], "count": pl.get('count', 0)} for pl in playlists]
        except Exception as e:
            logger.error(f"VK playlists fetch error: {e}")
            return []

    async def get_vk_playlist_tracks(self, playlist_id: int) -> List[Dict]:
        """Получение треков из плейлиста ВК"""
        if not self.vk_session:
            return []
        try:
            vk = self.vk_session.get_api()
            response = vk.audio.get(owner_id=None, album_id=playlist_id)
            tracks = response.get('items', [])
            return [{
                'title': f"{audio['artist']} - {audio['title']}",
                'artist': audio['artist'],
                'track': audio['title'],
                'duration': audio.get('duration', 0),
                'source': 'vk'
            } for audio in tracks]
        except Exception as e:
            logger.error(f"VK playlist tracks fetch error: {e}")
            return []

    async def get_yandex_playlists(self) -> List[Dict]:
        """Получение плейлистов из Яндекс.Музыки"""
        if not self.yandex_client:
            return []
        try:
            playlists = self.yandex_client.users_playlists()
            return [{"id": pl.kind, "title": pl.title, "count": pl.track_count} for pl in playlists if pl.track_count > 0]
        except Exception as e:
            logger.error(f"Yandex playlists fetch error: {e}")
            return []

    async def get_yandex_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """Получение треков из плейлиста Яндекс.Музыки"""
        if not self.yandex_client:
            return []
        try:
            playlists = self.yandex_client.users_playlists()
            target_playlist = next((pl for pl in playlists if pl.kind == playlist_id), None)
            if not target_playlist:
                return []
            tracks = target_playlist.fetch_tracks()
            return [{
                'title': f"{', '.join(tr.artists_name())} - {tr.title}",
                'artist': ', '.join(tr.artists_name()),
                'track': tr.title,
                'duration': tr.duration_ms // 1000 if tr.duration_ms else 0,
                'source': 'yandex'
            } for tr in tracks]
        except Exception as e:
            logger.error(f"Yandex playlist tracks fetch error: {e}")
            return []

class MusicDownloader:
    @staticmethod
    async def download_track(query: str) -> Optional[str]:
        """Скачивание трека из открытых источников интернета"""
        try:
            output_path = os.path.join(TEMP_DIR, f"temp_{int(asyncio.get_event_loop().time())}")

            # Настройки для поиска в открытых источниках
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

            # Поиск в открытых источниках (YouTube как пример открытого источника)
            search_query = f"ytsearch1:{query}"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)

                if not info.get('entries'):
                    return None

                video_info = info['entries'][0]
                duration = video_info.get('duration', 0)

                # Проверка ограничений
                if duration > MAX_DURATION:
                    logger.warning(f"Track too long: {duration}s > {MAX_DURATION}s")
                    return None

                # Скачивание
                ydl.download([video_info['webpage_url']])

                # Проверка результата
                mp3_file = f"{output_path}.mp3"
                if os.path.exists(mp3_file):
                    file_size = os.path.getsize(mp3_file)
                    if file_size <= MAX_FILE_SIZE:
                        return mp3_file
                    else:
                        os.remove(mp3_file)
                        logger.warning(f"File too large: {file_size} > {MAX_FILE_SIZE}")

                return None

        except Exception as e:
            logger.error(f"Error downloading {query}: {e}")
            return None

    @staticmethod
    def cleanup_file(file_path: str):
        """Удаление временного файла"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")

# Инициализация сервисов
music_service = TechnicalMusicService()
downloader = MusicDownloader()

# Создание клавиатур
def main_menu():
    """Главное меню бота"""
    keyboard = []

    # Поиск всегда доступен
    keyboard.append([InlineKeyboardButton(text="🔍 Поиск музыки", callback_data="search_music")])

    # ВК - если настроен
    if music_service.vk_audio:
        keyboard.append([InlineKeyboardButton(text="📂 Мои плейлисты ВК", callback_data="vk_playlists")])

    # Яндекс - если настроен  
    if music_service.yandex_client:
        keyboard.append([InlineKeyboardButton(text="📂 Мои плейлисты Яндекс", callback_data="yandex_playlists")])

    keyboard.append([InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def paginated_keyboard(items: List[Dict], prefix: str, page: int = 0, per_page: int = 5, show_download_all: bool = False):
    """Клавиатура с постраничной навигацией"""
    keyboard = []
    start = page * per_page
    end = min(start + per_page, len(items))

    # Элементы страницы
    for i in range(start, end):
        item = items[i]
        title = item['title'][:45] + "..." if len(item['title']) > 45 else item['title']
        keyboard.append([InlineKeyboardButton(text=f"🎵 {title}", callback_data=f"{prefix}_{i}_{page}")])

    # Кнопка "Скачать все" для треков
    if show_download_all and items:
        keyboard.append([InlineKeyboardButton(text="📥 Скачать все треки", callback_data=f"{prefix}_download_all_{page}")])

    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"{prefix}_page_{page-1}"))
    if end < len(items):
        nav_buttons.append(InlineKeyboardButton("➡️ Далее", callback_data=f"{prefix}_page_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Обработчики команд
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    """Команда /start"""
    await msg.answer(TEXTS["welcome"], reply_markup=main_menu(), parse_mode="Markdown")

@dp.message(Command("help"))  
async def help_cmd(msg: Message):
    """Команда /help"""
    await msg.answer(TEXTS["help"], parse_mode="Markdown")

# Обработчики callback-запросов
@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(query: CallbackQuery):
    """Возврат в главное меню"""
    await query.message.edit_text(TEXTS["welcome"], reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "help")
async def help_handler(query: CallbackQuery):
    """Справка"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])
    await query.message.edit_text(TEXTS["help"], reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "search_music")
async def search_music_handler(query: CallbackQuery, state: FSMContext):
    """Начало поиска музыки"""
    await query.message.edit_text(TEXTS["search_prompt"], parse_mode="Markdown")
    await state.set_state(MusicStates.waiting_search_query)

# Обработчики плейлистов ВК
@dp.callback_query(F.data == "vk_playlists")
async def vk_playlists_handler(query: CallbackQuery, state: FSMContext):
    """Показ плейлистов ВК"""
    if not music_service.vk_audio:
        await query.answer(TEXTS["service_not_configured"].format("ВКонтакте"), show_alert=True)
        return

    status_msg = await query.message.edit_text(TEXTS["vk_loading_playlists"], parse_mode="Markdown")

    playlists = await music_service.get_vk_playlists()
    if not playlists:
        await status_msg.edit_text(TEXTS["vk_no_playlists"], parse_mode="Markdown")
        return

    await state.update_data(vk_playlists=playlists)
    await status_msg.edit_text(
        TEXTS["vk_playlists_title"].format(len(playlists)),
        reply_markup=paginated_keyboard(playlists, "vkpl"),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("vkpl_"))
async def vk_playlist_select_handler(query: CallbackQuery, state: FSMContext):
    """Выбор плейлиста ВК"""
    parts = query.data.split("_")
    if len(parts) < 3:
        return

    idx = int(parts[1])
    page = int(parts[2])

    data = await state.get_data()
    playlists = data.get("vk_playlists", [])

    if idx >= len(playlists):
        await query.answer("❌ Плейлист не найден")
        return

    playlist = playlists[idx]
    status_msg = await query.message.edit_text(
        TEXTS["vk_loading_tracks"].format(playlist['title']), 
        parse_mode="Markdown"
    )

    tracks = await music_service.get_vk_playlist_tracks(playlist['id'])
    if not tracks:
        await status_msg.edit_text(TEXTS["vk_no_tracks"], parse_mode="Markdown")
        return

    await state.update_data(vk_tracks=tracks, current_playlist=playlist['title'])
    await status_msg.edit_text(
        TEXTS["vk_tracks_title"].format(playlist['title'], len(tracks)),
        reply_markup=paginated_keyboard(tracks, "vktr", 0, show_download_all=True),
        parse_mode="Markdown"
    )

# Обработчики плейлистов Яндекс
@dp.callback_query(F.data == "yandex_playlists")
async def yandex_playlists_handler(query: CallbackQuery, state: FSMContext):
    """Показ плейлистов Яндекс.Музыки"""
    if not music_service.yandex_client:
        await query.answer(TEXTS["service_not_configured"].format("Яндекс.Музыка"), show_alert=True)
        return

    status_msg = await query.message.edit_text(TEXTS["yandex_loading_playlists"], parse_mode="Markdown")

    playlists = await music_service.get_yandex_playlists()
    if not playlists:
        await status_msg.edit_text(TEXTS["yandex_no_playlists"], parse_mode="Markdown")
        return

    await state.update_data(yandex_playlists=playlists)
    await status_msg.edit_text(
        TEXTS["yandex_playlists_title"].format(len(playlists)),
        reply_markup=paginated_keyboard(playlists, "ypl"),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("ypl_"))
async def yandex_playlist_select_handler(query: CallbackQuery, state: FSMContext):
    """Выбор плейлиста Яндекс"""
    parts = query.data.split("_")
    if len(parts) < 3:
        return

    idx = int(parts[1])
    page = int(parts[2])

    data = await state.get_data()
    playlists = data.get("yandex_playlists", [])

    if idx >= len(playlists):
        await query.answer("❌ Плейлист не найден")
        return

    playlist = playlists[idx]
    status_msg = await query.message.edit_text(
        TEXTS["yandex_loading_tracks"].format(playlist['title']), 
        parse_mode="Markdown"
    )

    tracks = await music_service.get_yandex_playlist_tracks(playlist['id'])
    if not tracks:
        await status_msg.edit_text(TEXTS["yandex_no_tracks"], parse_mode="Markdown")
        return

    await state.update_data(yandex_tracks=tracks, current_playlist=playlist['title'])
    await status_msg.edit_text(
        TEXTS["yandex_tracks_title"].format(playlist['title'], len(tracks)),
        reply_markup=paginated_keyboard(tracks, "ytr", 0, show_download_all=True),
        parse_mode="Markdown"
    )

# Обработчики скачивания отдельных треков
@dp.callback_query(F.data.startswith(("vktr_", "ytr_")))
async def track_download_handler(query: CallbackQuery, state: FSMContext):
    """Скачивание отдельного трека"""
    parts = query.data.split("_")
    if len(parts) < 3:
        return

    prefix = parts[0]  # vktr или ytr
    idx = int(parts[1])
    page = int(parts[2])

    data = await state.get_data()
    tracks_key = f"{prefix.replace('tr', '')}_tracks"  # vk_tracks или yandex_tracks
    tracks = data.get(tracks_key, [])

    if idx >= len(tracks):
        await query.answer("❌ Трек не найден")
        return

    track = tracks[idx]
    current_playlist = data.get("current_playlist", "плейлист")

    # Уведомление о начале скачивания
    status_msg = await query.message.edit_text(
        TEXTS["searching"].format(track['title']),
        parse_mode="Markdown"
    )

    # Скачивание
    file_path = await downloader.download_track(track['title'])

    if file_path:
        await status_msg.edit_text(TEXTS["sending"].format(track['title']), parse_mode="Markdown")

        # Отправка аудиофайла
        try:
            with open(file_path, "rb") as audio_file:
                await query.message.answer_audio(
                    audio=audio_file,
                    caption=f"🎵 {track['title']}\n📂 Плейлист: {current_playlist}\n📍 Найдено в открытых источниках",
                    parse_mode="Markdown"
                )

            downloader.cleanup_file(file_path)

            # Возвращаемся к списку треков
            await status_msg.edit_text(
                TEXTS[f"{prefix.replace('tr', '')}_tracks_title"].format(current_playlist, len(tracks)),
                reply_markup=paginated_keyboard(tracks, prefix, page, show_download_all=True),
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            await status_msg.edit_text("❌ Ошибка отправки файла", parse_mode="Markdown")
    else:
        await status_msg.edit_text(TEXTS["not_found"].format(track['title']), parse_mode="Markdown")

# Обработчики скачивания всех треков
@dp.callback_query(F.data.startswith(("vktr_download_all", "ytr_download_all")))
async def download_all_tracks_handler(query: CallbackQuery, state: FSMContext):
    """Скачивание всех треков из плейлиста"""
    parts = query.data.split("_")
    prefix = parts[0]  # vktr или ytr

    data = await state.get_data()
    tracks_key = f"{prefix.replace('tr', '')}_tracks"
    tracks = data.get(tracks_key, [])
    current_playlist = data.get("current_playlist", "плейлист")

    if not tracks:
        await query.answer("❌ Нет треков для скачивания")
        return

    # Подтверждение
    await query.message.edit_text(
        TEXTS["downloading_playlist"].format(current_playlist, len(tracks)),
        parse_mode="Markdown"
    )

    # Счетчики
    downloaded_count = 0
    failed_count = 0

    # Скачивание треков по очереди
    for i, track in enumerate(tracks):
        # Обновление прогресса
        progress_msg = TEXTS["playlist_progress"].format(i + 1, len(tracks), track['title'])
        await query.message.edit_text(progress_msg, parse_mode="Markdown")

        # Скачивание трека
        file_path = await downloader.download_track(track['title'])

        if file_path:
            try:
                # Отправка аудиофайла
                with open(file_path, "rb") as audio_file:
                    await query.message.answer_audio(
                        audio=audio_file,
                        caption=f"🎵 {track['title']}\n📂 {current_playlist} ({i+1}/{len(tracks)})\n📍 Найдено в открытых источниках",
                        parse_mode="Markdown"
                    )

                downloader.cleanup_file(file_path)
                downloaded_count += 1

            except Exception as e:
                logger.error(f"Error sending audio {track['title']}: {e}")
                failed_count += 1
        else:
            failed_count += 1

        # Небольшая пауза между скачиваниями
        await asyncio.sleep(1)

    # Финальный отчет
    await query.message.edit_text(
        TEXTS["playlist_completed"].format(downloaded_count, failed_count),
        parse_mode="Markdown"
    )

    # Возврат в главное меню через 3 секунды
    await asyncio.sleep(3)
    await query.message.edit_text(TEXTS["welcome"], reply_markup=main_menu(), parse_mode="Markdown")

# Навигация по страницам
@dp.callback_query(F.data.startswith(("vkpl_page_", "vktr_page_", "ypl_page_", "ytr_page_")))
async def page_navigation_handler(query: CallbackQuery, state: FSMContext):
    """Навигация по страницам"""
    parts = query.data.split("_")
    prefix = "_".join(parts[:-2])
    page = int(parts[-1])

    data = await state.get_data()

    if prefix == "vkpl":
        items = data.get("vk_playlists", [])
        text = TEXTS["vk_playlists_title"].format(len(items))
        show_download_all = False
    elif prefix == "vktr":
        items = data.get("vk_tracks", [])
        current_playlist = data.get("current_playlist", "плейлист")
        text = TEXTS["vk_tracks_title"].format(current_playlist, len(items))
        show_download_all = True
    elif prefix == "ypl":
        items = data.get("yandex_playlists", [])
        text = TEXTS["yandex_playlists_title"].format(len(items))
        show_download_all = False
    elif prefix == "ytr":
        items = data.get("yandex_tracks", [])
        current_playlist = data.get("current_playlist", "плейлист")
        text = TEXTS["yandex_tracks_title"].format(current_playlist, len(items))
        show_download_all = True
    else:
        await query.answer("❌ Ошибка навигации")
        return

    await query.message.edit_text(
        text,
        reply_markup=paginated_keyboard(items, prefix, page, show_download_all=show_download_all),
        parse_mode="Markdown"
    )

# Обработчик поискового состояния
@dp.message(MusicStates.waiting_search_query)
async def process_search_query(msg: Message, state: FSMContext):
    """Обработка поискового запроса"""
    query = msg.text.strip()

    # Валидация запроса
    if len(query) < 2:
        await msg.answer(TEXTS["too_short"])
        return

    if len(query) > 100:
        await msg.answer(TEXTS["too_long"])
        return

    # Поиск и скачивание
    status_msg = await msg.answer(TEXTS["searching"].format(query), parse_mode="Markdown")

    try:
        file_path = await downloader.download_track(query)

        if file_path:
            await status_msg.edit_text(TEXTS["sending"].format(query), parse_mode="Markdown")

            # Отправка аудиофайла
            with open(file_path, "rb") as audio_file:
                await msg.answer_audio(
                    audio=audio_file,
                    caption=f"🎵 {query}\n📍 Найдено в открытых источниках интернета",
                    parse_mode="Markdown"
                )

            downloader.cleanup_file(file_path)

            # Удаляем статусное сообщение
            try:
                await status_msg.delete()
            except:
                pass
        else:
            await status_msg.edit_text(TEXTS["not_found"].format(query), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing search query '{query}': {e}")
        await status_msg.edit_text(TEXTS["error"], parse_mode="Markdown")

    await state.clear()

    # Показываем главное меню
    await asyncio.sleep(1)
    await msg.answer(TEXTS["welcome"], reply_markup=main_menu(), parse_mode="Markdown")

# Обработчик обычных сообщений (прямой поиск)
@dp.message(F.text & ~F.text.startswith('/'))
async def direct_search_handler(message: Message):
    """Прямой поиск без команд"""
    query = message.text.strip()

    # Проверка длины
    if len(query) < 2:
        await message.answer(TEXTS["too_short"])
        return

    if len(query) > 100:
        await message.answer(TEXTS["too_long"])
        return

    # Исключаем обычные фразы
    excluded = ['привет', 'hello', 'как дела', 'спасибо', 'пока', 'hi', 'hey', 'добрый день', 'добрый вечер']
    if any(word in query.lower() for word in excluded):
        await message.answer("👋 Привет! Напишите название трека для поиска или используйте меню.", reply_markup=main_menu())
        return

    # Поиск и скачивание
    status_msg = await message.answer(TEXTS["searching"].format(query), parse_mode="Markdown")

    try:
        file_path = await downloader.download_track(query)

        if file_path:
            await status_msg.edit_text(TEXTS["sending"].format(query), parse_mode="Markdown")

            # Отправка аудиофайла
            with open(file_path, "rb") as audio_file:
                await message.answer_audio(
                    audio=audio_file,
                    caption=f"🎵 {query}\n📍 Найдено в открытых источниках интернета",
                    parse_mode="Markdown"
                )

            downloader.cleanup_file(file_path)

            # Удаляем статусное сообщение
            try:
                await status_msg.delete()
            except:
                pass
        else:
            await status_msg.edit_text(TEXTS["not_found"].format(query), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in direct search '{query}': {e}")
        await status_msg.edit_text(TEXTS["error"], parse_mode="Markdown")

async def main():
    """Запуск бота"""
    try:
        logger.info("🎵 Starting Music Telegram Bot...")

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

        # Проверка сервисов
        services_status = []
        if music_service.vk_audio:
            services_status.append("✅ VK")
        if music_service.yandex_client:
            services_status.append("✅ Yandex Music")

        if services_status:
            logger.info(f"📱 Available services: {', '.join(services_status)}")
        else:
            logger.info("📱 Only direct search available (no VK/Yandex tokens)")

        logger.info("🚀 Bot started successfully!")
        await dp.start_polling(bot, skip_updates=True)

    except Exception as e:
        logger.error(f"❌ Bot startup error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
