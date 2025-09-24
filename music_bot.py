import os
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import Optional
import time
import urllib.parse
import re

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

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_FILE_SIZE = 50 * 1024 * 1024  
MAX_DURATION = 600  
TEMP_DIR = tempfile.gettempdir()

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Texts
TEXTS = {
    "welcome": """🎵 **Музыкальный бот** с multi-source поиском

Что я умею:
• 🔍 Ищу музыку в YouTube, Zaycev.net, альтернативных источниках
• 📤 Отправляю MP3 (до 50MB, до 10 минут)

Просто напишите название трека или исполнителя.

Примеры:
• Imagine Dragons Radioactive
• The Beatles Hey Jude
• Монеточка Каждый раз

Выберите:”"",
    "help": """ **Справка**

Команды:
/start — главное меню
/help — эта справка

После /start нажмите 🔍 Поиск музыки и отправьте название.""",
    "search_prompt": "🔍 Отправьте название трека для поиска:",
    "searching_youtube": "🎥 Ищу на YouTube: {}",
    "searching_zaycev": "🎵 Ищу на Zaycev.net: {}",
    "searching_alternative": "🔍 Ищу альтернативные источники: {}",
    "sending": "📤 Отправляю: {}",
    "not_found_anywhere": "❌ Не найдено: {}",
    "too_short": "❌ Слишком короткий запрос (мин 2 символа).",
    "too_long": "❌ Слишком длинный запрос (макс 100 символов).",
    "too_long_track": "❌ Трек длиннее 10 минут.",
    "too_big_file": "❌ Файл больше 50MB.",
    "error": "❌ Ошибка при поиске."
}

class MusicStates(StatesGroup):
    waiting_search = State()

class MultiSourceDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0'
        })

    async def search_youtube(self, query: str) -> Optional[str]:
        logger.info(f"YouTube search: {query}")
        output = os.path.join(TEMP_DIR, f"yt_{int(time.time())}")
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': f'{output}.%(ext)s',
            'quiet': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '192',
            'prefer_ffmpeg': True,
            'socket_timeout': 30,
            'postprocessors': [{'key': 'FFmpegExtractAudio'}],
            'cookiefile': 'youtube_cookies.txt'
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if not info or not info.get('entries'): return None
                vid = info['entries'][0]
                if vid.get('duration',0) > MAX_DURATION: return "TOO_LONG"
                ydl.download([vid['webpage_url']])
                mp3 = f"{output}.mp3"
                if os.path.exists(mp3):
                    if os.path.getsize(mp3) <= MAX_FILE_SIZE: return mp3
                    os.remove(mp3)
                    return "TOO_BIG"
        except Exception as e:
            logger.error(f"YouTube error: {e}")
        return None

    async def search_zaycev(self, query: str) -> Optional[str]:
        logger.info(f"Zaycev search: {query}")
        url = f"https://zaycev.net/search.html?query_search={urllib.parse.quote(query)}"
        try:
            r = self.session.get(url, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            elems = soup.select('div.musicset__item') or soup.select('div.music-item')
            if not elems: return None
            link = elems[0].select_one('a[href*="/music/"]')
            if not link: return None
            track_url = "https://zaycev.net" + link['href']
            r2 = self.session.get(track_url, timeout=20); r2.raise_for_status()
            soup2 = BeautifulSoup(r2.text, "html.parser")
            dl = None
            audio = soup2.select_one('audio source[src*=".mp3"]')
            if audio: dl = audio['src']
            if not dl:
                data = soup2.select_one('[data-url*=".mp3"]')
                if data: dl = data['data-url']
            if not dl:
                btn = soup2.select_one('a[href*=".mp3"]')
                if btn: dl = btn['href']
            if not dl:
                # JS search
                for s in soup2.find_all('script'):
                    if s.string and '.mp3' in s.string:
                        m = re.findall(r'["\']([^"\']*\.mp3[^"\']*)["\']', s.string)
                        if m:
                            dl = m[0]; break
            if not dl: return None
            if dl.startswith('//'): dl = 'https:' + dl
            if dl.startswith('/'): dl = 'https://zaycev.net' + dl
            tmp = os.path.join(TEMP_DIR, f"z_{int(time.time())}.mp3")
            ar = self.session.get(dl, timeout=30, stream=True); ar.raise_for_status()
            ct = ar.headers.get('content-type','')
            if 'audio' not in ct and 'octet-stream' not in ct: return None
            with open(tmp,'wb') as f:
                for c in ar.iter_content(8192): f.write(c)
            sz = os.path.getsize(tmp)
            if sz<1000: os.remove(tmp); return None
            if sz>MAX_FILE_SIZE: os.remove(tmp); return "TOO_BIG"
            return tmp
        except Exception as e:
            logger.error(f"Zaycev error: {e}")
        return None

    async def search_alternative(self, query: str) -> Optional[str]:
        logger.info(f"Alternative search: {query}")
        for q in [f"ytsearch1:{query} site:soundcloud.com", f"ytsearch1:{query} audio"]:
            output = os.path.join(TEMP_DIR, f"alt_{int(time.time())}")
            opts = {'format':'bestaudio/best','outtmpl':f'{output}.%(ext)s','quiet':True,'postprocessors':[{'key':'FFmpegExtractAudio'}]}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(q, download=False)
                    if not info or not info.get('entries'): continue
                    vid = info['entries'][0]
                    if vid.get('duration',0)>MAX_DURATION: continue
                    ydl.download([vid['webpage_url']])
                    mp3 = f"{output}.mp3"
                    if os.path.exists(mp3) and os.path.getsize(mp3)<=MAX_FILE_SIZE:
                        return mp3
                    if os.path.exists(mp3): os.remove(mp3)
            except: pass
            await asyncio.sleep(1)
        return None

    async def download_track(self, query:str, status_cb=None)->(Optional[str],str):
        for name,key,func in [("YouTube","searching_youtube",self.search_youtube),
                              ("Zaycev.net","searching_zaycev",self.search_zaycev),
                              ("Alternative","searching_alternative",self.search_alternative)]:
            try:
                if status_cb: await status_cb(key,query)
                res = await func(query)
                if res=="TOO_LONG": return "TOO_LONG",name
                if res=="TOO_BIG": return "TOO_BIG",name
                if res: return res,name
            except Exception as e:
                logger.error(f"{name} error: {e}")
        return None,"nowhere"

    def cleanup(self,path):
        try:
            if path and os.path.exists(path): os.remove(path)
        except: pass

downloader = MultiSourceDownloader()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🔍 Поиск музыки",callback_data="search")],
        [InlineKeyboardButton("ℹ️ Помощь",callback_data="help")]
    ])

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🏠 Главное меню",callback_data="start")]
    ])

@dp.message(Command("start"))
async def cmd_start(m:Message):
    await m.answer(TEXTS["welcome"],reply_markup=main_menu(),parse_mode="Markdown")

@dp.message(Command("help"))
async def cmd_help(m:Message):
    await m.answer(TEXTS["help"],reply_markup=back_menu(),parse_mode="Markdown")

@dp.callback_query(F.data=="start")
async def cb_start(q:CallbackQuery):
    await q.message.edit_text(TEXTS["welcome"],reply_markup=main_menu(),parse_mode="Markdown")

@dp.callback_query(F.data=="help")
async def cb_help(q:CallbackQuery):
    await q.message.edit_text(TEXTS["help"],reply_markup=back_menu(),parse_mode="Markdown")

@dp.callback_query(F.data=="search")
async def cb_search(q:CallbackQuery,state:FSMContext):
    await q.message.edit_text(TEXTS["search_prompt"],parse_mode="Markdown")
    await state.set_state(MusicStates.waiting_search)

async def process_search(m:Message,query:str,is_state:bool):
    if len(query)<2:
        await m.answer(TEXTS["too_short"]);return
    if len(query)>100:
        await m.answer(TEXTS["too_long"]);return
    status=await m.answer("🔍 Ищу...",parse_mode="Markdown")
    async def upd(key,txt):
        txt2=TEXTS.get(key,txt).format(txt)
        await status.edit_text(txt2,parse_mode="Markdown")
    res,src=await downloader.download_track(query,upd)
    if res=="TOO_LONG":
        await status.edit_text(TEXTS["too_long_track"],parse_mode="Markdown")
    elif res=="TOO_BIG":
        await status.edit_text(TEXTS["too_big_file"],parse_mode="Markdown")
    elif res:
        await status.edit_text(TEXTS["sending"].format(query),parse_mode="Markdown")
        with open(res,"rb") as f:
            await m.answer_audio(f,caption=f"🎵 {query}\n✅ Найдено на: {src}")
        downloader.cleanup(res)
        try: await status.delete()
        except: pass
        if not is_state:
            await m.answer("✅ Готово! Еще поиск?",reply_markup=main_menu())
    else:
        await status.edit_text(TEXTS["not_found_anywhere"].format(query),parse_mode="Markdown")

@dp.message(MusicStates.waiting_search)
async def st_search(m:Message,state:FSMContext):
    q=m.text.strip()
    await process_search(m,q,True)
    await state.clear()
    await asyncio.sleep(1)
    await m.answer(TEXTS["welcome"],reply_markup=main_menu(),parse_mode="Markdown")

@dp.message(F.text & ~F.text.startswith("/"))
async def direct(m:Message):
    await process_search(m,m.text,False)

async def main():
    logger.info("🚀 Bot start")
    Path(TEMP_DIR).mkdir(exist_ok=True)
    await dp.start_polling(bot,skip_updates=True)

if __name__=="__main__":
    asyncio.run(main())
