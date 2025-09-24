# Сохранем основной код бота в отдельный файл
bot_code = '''import os
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN", "")
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB Telegram limit
MAX_DURATION = 600  # 10 minutes max duration
TEMP_DIR = tempfile.gettempdir()

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class MusicStates(StatesGroup):
    browsing_vk_playlists = State()
    browsing_vk_tracks = State()
    browsing_yandex_playlists = State()
    browsing_yandex_tracks = State()
    waiting_search_query = State()

class TechnicalMusicService:
    def __init__(self):
        self.vk_session = None
        self.vk_audio = None
        self.yandex_client = None
        self.init_services()

    def init_services(self):
        if VK_ACCESS_TOKEN:
            try:
                session = vk_api.VkApi(token=VK_ACCESS_TOKEN)
                self.vk_audio = VkAudio(session)
                self.vk_session = session
                logger.info("✅ VK service initialized")
            except Exception as e:
                logger.error(f"VK init error: {e}")

        if YANDEX_TOKEN:
            try:
                self.yandex_client = yandex_music.Client(YANDEX_TOKEN).init()
                logger.info("✅ Yandex Music service initialized")
            except Exception as e:
                logger.error(f"Yandex init error: {e}")

    async def get_vk_playlists(self) -> List[Dict]:
        if not self.vk_session:
            return []
        try:
            vk = self.vk_session.get_api()
            response = vk.audio.getPlaylists(owner_id=None)
            playlists = response['items']
            return [{"id": pl['id'], "title": pl['title']} for pl in playlists]
        except Exception as e:
            logger.error(f"VK playlists fetch error: {e}")
            return []

    async def get_vk_playlist_tracks(self, playlist_id: int) -> List[Dict]:
        if not self.vk_session:
            return []
        try:
            vk = self.vk_session.get_api()
            response = vk.audio.get(owner_id=None, album_id=playlist_id)
            tracks = response['items']
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
        if not self.yandex_client:
            return []
        try:
            playlists = self.yandex_client.users_playlists()
            return [{"id": pl.kind, "title": pl.title} for pl in playlists]
        except Exception as e:
            logger.error(f"Yandex playlists fetch error: {e}")
            return []

    async def get_yandex_playlist_tracks(self, playlist_id: str) -> List[Dict]:
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
        try:
            output_path = os.path.join(TEMP_DIR, f"temp_{int(asyncio.get_event_loop().time())}")
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
                if not info.get('entries'):
                    return None
                video_info = info['entries'][0]
                duration = video_info.get('duration', 0)
                if duration > MAX_DURATION:
                    return None
                ydl.download([video_info['webpage_url']])
                mp3_file = f"{output_path}.mp3"
                if os.path.exists(mp3_file):
                    file_size = os.path.getsize(mp3_file)
                    if file_size <= MAX_FILE_SIZE:
                        return mp3_file
                    else:
                        os.remove(mp3_file)
                return None
        except Exception as e:
            logger.error(f"Error downloading {query}: {e}")
            return None

    @staticmethod
    def cleanup_file(file_path: str):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")

music_service = TechnicalMusicService()
downloader = MusicDownloader()

# --- Keyboards ---
def main_menu():
    keyboard = []
    keyboard.append([InlineKeyboardButton(text="🔍 Поиск музыки", callback_data="search_music")])
    if music_service.vk_audio:
        keyboard.append([InlineKeyboardButton(text="📂 Мои плейлисты ВК", callback_data="vk_playlists")])
    if music_service.yandex_client:
        keyboard.append([InlineKeyboardButton(text="📂 Мои плейлисты Яндекс", callback_data="yandex_playlists")])
    keyboard.append([InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def paginated_keyboard(items: List[Dict], prefix: str, page: int = 0, per_page=5):
    keyboard = []
    start = page * per_page
    end = min(start + per_page, len(items))
    for i in range(start, end):
        item = items[i]
        key = f"{prefix}_{i}_{page}"
        keyboard.append([InlineKeyboardButton(text=item['title'][:50], callback_data=key)])
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}_page_{page-1}"))
    if end < len(items):
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}_page_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- Handlers ---

@dp.message(Command("start"))
async def start_cmd(msg: Message):
    welcome_text = """🎵 **Добро пожаловать в музыкального бота!**

**Возможности:**
• 🔍 Поиск и скачивание музыки с YouTube
• 📂 Доступ к плейлистам ВКонтакте  
• 📂 Доступ к плейлистам Яндекс.Музыки
• 🎵 Высокое качество MP3 (192kbps)
• ⚡ Быстрая загрузка и отправка

Выберите действие из меню ниже:"""
    await msg.answer(welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(query: CallbackQuery):
    await query.message.edit_text("🎵 **Главное меню**\\n\\nВыберите действие:", 
                                  reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "search_music")
async def search_music_handler(query: CallbackQuery, state: FSMContext):
    search_text = """🔍 **Поиск музыки**

Отправьте название трека, который хотите найти.

**Примеры:**
• Imagine Dragons Radioactive
• The Beatles Hey Jude  
• Eminem Lose Yourself

Бот найдет трек на YouTube и отправит аудиофайл."""
    await query.message.edit_text(search_text, parse_mode="Markdown")
    await state.set_state(MusicStates.waiting_search_query)

@dp.message(MusicStates.waiting_search_query)
async def process_search_query(msg: Message, state: FSMContext):
    query = msg.text.strip()
    
    # Проверка длины запроса
    if len(query) < 2:
        await msg.answer("❌ Слишком короткий запрос. Минимум 2 символа.")
        return
    
    status_msg = await msg.answer(f"🔍 Ищу: **{query}**\\n\\n⏳ Скачиваю с YouTube...", 
                                  parse_mode="Markdown")
    
    file_path = await downloader.download_track(query)
    if file_path:
        await status_msg.edit_text(f"📤 Отправляю: **{query}**", parse_mode="Markdown")
        
        with open(file_path, "rb") as audio_file:
            await msg.answer_audio(
                audio=audio_file,
                caption=f"🎵 {query}\\n📍 Источник: YouTube",
                parse_mode="Markdown"
            )
        downloader.cleanup_file(file_path)
        
        # Удаляем сообщение о статусе
        try:
            await status_msg.delete()
        except:
            pass
    else:
        await status_msg.edit_text(f"❌ Не найден: **{query}**\\n\\nПопробуйте изменить запрос.", 
                                   parse_mode="Markdown")
    
    await state.clear()
    
    # Возвращаем главное меню
    await asyncio.sleep(1)
    await msg.answer("🎵 **Главное меню**", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "vk_playlists")
async def vk_playlists_handler(query: CallbackQuery, state: FSMContext):
    if not music_service.vk_audio:
        await query.answer("❌ ВК сервис не настроен", show_alert=True)
        return
        
    status_msg = await query.message.edit_text("🔄 Загружаю плейлисты ВК...")
    
    playlists = await music_service.get_vk_playlists()
    if not playlists:
        await status_msg.edit_text("❌ Не удалось получить плейлисты ВК")
        return
        
    await state.update_data(vk_playlists=playlists)
    
    playlist_text = f"📂 **Ваши плейлисты ВК** ({len(playlists)} шт.)\\n\\nВыберите плейлист:"
    await status_msg.edit_text(playlist_text, 
                               reply_markup=paginated_keyboard(playlists, "vkpl"),
                               parse_mode="Markdown")

@dp.callback_query(F.data.startswith("vkpl_"))
async def vk_playlist_select_handler(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    playlists = data.get("vk_playlists", [])
    parts = query.data.split("_")
    idx = int(parts[1])
    page = int(parts[2])
    
    if idx >= len(playlists):
        await query.answer("❌ Плейлист не найден")
        return
        
    playlist = playlists[idx]
    
    status_msg = await query.message.edit_text(f"🔄 Загружаю треки из: **{playlist['title']}**", 
                                               parse_mode="Markdown")
    
    tracks = await music_service.get_vk_playlist_tracks(playlist['id'])
    if not tracks:
        await status_msg.edit_text("❌ Не удалось получить треки плейлиста")
        return
        
    await state.update_data(vk_tracks=tracks, current_playlist=playlist['title'])
    
    tracks_text = f"🎵 **{playlist['title']}** ({len(tracks)} треков)\\n\\nВыберите трек для скачивания:"
    await status_msg.edit_text(tracks_text, 
                               reply_markup=paginated_keyboard(tracks, "vktr", 0),
                               parse_mode="Markdown")

@dp.callback_query(F.data.startswith("vktr_"))
async def vk_track_select_handler(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tracks = data.get("vk_tracks", [])
    current_playlist = data.get("current_playlist", "плейлист")
    parts = query.data.split("_")
    idx = int(parts[1])
    page = int(parts[2])
    
    if idx >= len(tracks):
        await query.answer("❌ Трек не найден")
        return
        
    track = tracks[idx]
    
    status_msg = await query.message.edit_text(
        f"🔄 Скачиваю: **{track['title']}**\\n\\n⏳ Поиск на YouTube...",
        parse_mode="Markdown"
    )
    
    file_path = await downloader.download_track(track['title'])
    if file_path:
        await status_msg.edit_text(f"📤 Отправляю: **{track['title']}**", parse_mode="Markdown")
        
        with open(file_path, "rb") as audio_file:
            await query.message.answer_audio(
                audio=audio_file,
                caption=f"🎵 {track['title']}\\n📂 Плейлист: {current_playlist}\\n📍 Источник: ВК → YouTube",
                parse_mode="Markdown"
            )
        downloader.cleanup_file(file_path)
    else:
        await query.answer("❌ Не удалось скачать трек", show_alert=True)
    
    # Возвращаемся к списку треков
    tracks_text = f"🎵 **{current_playlist}** ({len(tracks)} треков)\\n\\nВыберите следующий трек:"
    await status_msg.edit_text(tracks_text, 
                               reply_markup=paginated_keyboard(tracks, "vktr", page),
                               parse_mode="Markdown")

@dp.callback_query(F.data == "yandex_playlists")
async def yandex_playlists_handler(query: CallbackQuery, state: FSMContext):
    if not music_service.yandex_client:
        await query.answer("❌ Яндекс.Музыка сервис не настроен", show_alert=True)
        return
        
    status_msg = await query.message.edit_text("🔄 Загружаю плейлисты Яндекс.Музыки...")
    
    playlists = await music_service.get_yandex_playlists()
    if not playlists:
        await status_msg.edit_text("❌ Не удалось получить плейлисты Яндекс.Музыки")
        return
        
    await state.update_data(yandex_playlists=playlists)
    
    playlist_text = f"📂 **Ваши плейлисты Яндекс.Музыки** ({len(playlists)} шт.)\\n\\nВыберите плейлист:"
    await status_msg.edit_text(playlist_text, 
                               reply_markup=paginated_keyboard(playlists, "ypl"),
                               parse_mode="Markdown")

@dp.callback_query(F.data.startswith("ypl_"))
async def yandex_playlist_select_handler(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    playlists = data.get("yandex_playlists", [])
    parts = query.data.split("_")
    idx = int(parts[1])
    page = int(parts[2])
    
    if idx >= len(playlists):
        await query.answer("❌ Плейлист не найден")
        return
        
    playlist = playlists[idx]
    
    status_msg = await query.message.edit_text(f"🔄 Загружаю треки из: **{playlist['title']}**", 
                                               parse_mode="Markdown")
    
    tracks = await music_service.get_yandex_playlist_tracks(playlist['id'])
    if not tracks:
        await status_msg.edit_text("❌ Не удалось получить треки плейлиста")
        return
        
    await state.update_data(yandex_tracks=tracks, current_playlist=playlist['title'])
    
    tracks_text = f"🎵 **{playlist['title']}** ({len(tracks)} треков)\\n\\nВыберите трек для скачивания:"
    await status_msg.edit_text(tracks_text, 
                               reply_markup=paginated_keyboard(tracks, "ytr", 0),
                               parse_mode="Markdown")

@dp.callback_query(F.data.startswith("ytr_"))
async def yandex_track_select_handler(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tracks = data.get("yandex_tracks", [])
    current_playlist = data.get("current_playlist", "плейлист")
    parts = query.data.split("_")
    idx = int(parts[1])
    page = int(parts[2])
    
    if idx >= len(tracks):
        await query.answer("❌ Трек не найден")
        return
        
    track = tracks[idx]
    
    status_msg = await query.message.edit_text(
        f"🔄 Скачиваю: **{track['title']}**\\n\\n⏳ Поиск на YouTube...",
        parse_mode="Markdown"
    )
    
    file_path = await downloader.download_track(track['title'])
    if file_path:
        await status_msg.edit_text(f"📤 Отправляю: **{track['title']}**", parse_mode="Markdown")
        
        with open(file_path, "rb") as audio_file:
            await query.message.answer_audio(
                audio=audio_file,
                caption=f"🎵 {track['title']}\\n📂 Плейлист: {current_playlist}\\n📍 Источник: Яндекс → YouTube",
                parse_mode="Markdown"
            )
        downloader.cleanup_file(file_path)
    else:
        await query.answer("❌ Не удалось скачать трек", show_alert=True)
    
    # Возвращаемся к списку треков
    tracks_text = f"🎵 **{current_playlist}** ({len(tracks)} треков)\\n\\nВыберите следующий трек:"
    await status_msg.edit_text(tracks_text, 
                               reply_markup=paginated_keyboard(tracks, "ytr", page),
                               parse_mode="Markdown")

# Навигация по страницам
@dp.callback_query(F.data.startswith(("vkpl_page_", "vktr_page_", "ypl_page_", "ytr_page_")))
async def page_navigation_handler(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parts = query.data.split("_")
    prefix = "_".join(parts[:-2])  # vkpl, vktr, ypl, ytr
    page = int(parts[-1])
    
    if prefix == "vkpl":
        items = data.get("vk_playlists", [])
        text = f"📂 **Ваши плейлисты ВК** ({len(items)} шт.)\\n\\nВыберите плейлист:"
    elif prefix == "vktr":
        items = data.get("vk_tracks", [])
        current_playlist = data.get("current_playlist", "плейлист")
        text = f"🎵 **{current_playlist}** ({len(items)} треков)\\n\\nВыберите трек для скачивания:"
    elif prefix == "ypl":
        items = data.get("yandex_playlists", [])
        text = f"📂 **Ваши плейлисты Яндекс.Музыки** ({len(items)} шт.)\\n\\nВыберите плейлист:"
    elif prefix == "ytr":
        items = data.get("yandex_tracks", [])
        current_playlist = data.get("current_playlist", "плейлист")
        text = f"🎵 **{current_playlist}** ({len(items)} треков)\\n\\nВыберите трек для скачивания:"
    else:
        await query.answer("❌ Ошибка навигации")
        return
    
    await query.message.edit_text(text, 
                                  reply_markup=paginated_keyboard(items, prefix, page),
                                  parse_mode="Markdown")

@dp.callback_query(F.data == "help")
async def help_handler(query: CallbackQuery):
    # Проверяем статус сервисов
    services_status = []
    if music_service.vk_audio:
        services_status.append("✅ ВКонтакте")
    else:
        services_status.append("❌ ВКонтакте (не настроен)")
        
    if music_service.yandex_client:
        services_status.append("✅ Яндекс.Музыка")  
    else:
        services_status.append("❌ Яндекс.Музыка (не настроен)")
    
    help_text = f"""🆘 **Справка по музыкальному боту**

**Доступные сервисы:**
{chr(10).join(services_status)}

**Возможности:**
🔍 **Поиск музыки** - найти любой трек на YouTube
📂 **Плейлисты ВК** - доступ к вашим плейлистам ВКонтакте
📂 **Плейлисты Яндекс** - доступ к плейлистам Яндекс.Музыки

**Как пользоваться:**
1. Выберите "🔍 Поиск музыки" для поиска треков
2. Отправьте название трека (например: "Imagine Dragons Radioactive")
3. Или выберите плейлист из ВК/Яндекс для просмотра треков

**Технические особенности:**
• Качество: MP3 192kbps
• Максимальный размер: 50MB
• Максимальная длительность: 10 минут
• Источник загрузки: YouTube

**Команды:**
/start - главное меню
/help - эта справка

**Технические аккаунты:**
Бот использует технические токены для безопасного доступа к ВК и Яндекс.Музыке без необходимости вводить личные данные."""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])
    
    await query.message.edit_text(help_text, reply_markup=keyboard, parse_mode="Markdown")

# Обработчик обычных сообщений (поиск вне состояния)
@dp.message(F.text & ~F.text.startswith('/'))
async def direct_search_handler(message: Message):
    query = message.text.strip()
    
    # Проверка длины запроса
    if len(query) < 2:
        await message.answer("❌ Слишком короткий запрос. Используйте меню для поиска.", 
                           reply_markup=main_menu())
        return
    
    # Исключаем обычные фразы
    excluded = ['привет', 'hello', 'как дела', 'спасибо', 'пока', 'hi', 'hey']
    if any(word in query.lower() for word in excluded):
        await message.answer("👋 Привет! Используйте меню для поиска музыки.", 
                           reply_markup=main_menu())
        return
    
    status_msg = await message.answer(f"🔍 Ищу: **{query}**\\n\\n⏳ Скачиваю с YouTube...", 
                                      parse_mode="Markdown")
    
    try:
        file_path = await downloader.download_track(query)
        if file_path:
            await status_msg.edit_text(f"📤 Отправляю: **{query}**", parse_mode="Markdown")
            
            with open(file_path, "rb") as audio_file:
                await message.answer_audio(
                    audio=audio_file,
                    caption=f"🎵 {query}\\n📍 Источник: YouTube",
                    parse_mode="Markdown"
                )
            downloader.cleanup_file(file_path)
            
            # Удаляем сообщение о статусе
            try:
                await status_msg.delete()
            except:
                pass
        else:
            await status_msg.edit_text(f"❌ Не найден: **{query}**\\n\\nИспользуйте меню для других вариантов.", 
                                       parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in direct search {query}: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при поиске")

async def main():
    try:
        logger.info("🎵 Starting Music Telegram Bot...")
        
        # Проверяем наличие необходимых переменных
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN not found in environment variables!")
            return
        
        # Создаем временную директорию
        Path(TEMP_DIR).mkdir(exist_ok=True)
        
        # Проверяем FFmpeg
        import shutil
        if not shutil.which('ffmpeg'):
            logger.warning("⚠️ FFmpeg not found! Audio conversion may not work properly.")
        else:
            logger.info("✅ FFmpeg found")
        
        logger.info("🚀 Bot started successfully!")
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Bot startup error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
'''

# Сохраняем основной код бота
with open('music_bot.py', 'w', encoding='utf-8') as f:
    f.write(bot_code)

print("✅ Создан основной файл music_bot.py")
print("\n🎉 ПОЛНАЯ СТРУКТУРА ПРОЕКТА ГОТОВА!")
print("\n📁 Файлы проекта:")
print("├── music_bot.py              # 🐍 Основной код бота")
print("├── requirements.txt          # 📦 Python зависимости") 
print("├── .env.example             # ⚙️ Пример конфигурации")
print("├── .gitignore               # 🚫 Git исключения")
print("├── README.md                # 📖 Документация")
print("├── Dockerfile               # 🐳 Docker образ")
print("├── docker-compose.yml       # 🐳 Docker Compose")
print("├── railway.json             # 🚂 Railway деплой")
print("├── Procfile                 # 📦 Heroku деплой")
print("└── .github/workflows/       # 🔄 CI/CD")
print("    └── deploy.yml")

print("\n🚀 СЛЕДУЮЩИЕ ШАГИ:")
print("1. 📋 Скопировать .env.example → .env")
print("2. 🔑 Заполнить токены в .env файле:")
print("   - BOT_TOKEN (от @BotFather)")
print("   - VK_ACCESS_TOKEN (опционально)")
print("   - YANDEX_TOKEN (опционально)")
print("3. 📦 Установить зависимости: pip install -r requirements.txt")
print("4. ▶️ Запустить локально: python music_bot.py")
print("5. 🌐 Для деплоя: push в GitHub → Railway автодеплой")

print("\n💡 ВОЗМОЖНОСТИ БОТА:")
print("✅ Поиск и скачивание музыки с YouTube")
print("✅ Доступ к плейлистам ВКонтакте") 
print("✅ Доступ к плейлистам Яндекс.Музыки")
print("✅ Интерактивное меню с навигацией")
print("✅ Высокое качество MP3 (192kbps)")
print("✅ Безопасная работа через технические токены")
print("✅ Полностью бесплатное решение")