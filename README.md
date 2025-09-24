# 🎵 Музыкальный Telegram Бот

Полнофункциональный бот для поиска, скачивания и отправки музыки в Telegram с поддержкой ВКонтакте и Яндекс.Музыки.

## ✨ Возможности

- 🔍 **Поиск музыки** по названию с YouTube
- 📂 **Плейлисты ВКонтакте** - доступ к вашим плейлистам
- 📂 **Плейлисты Яндекс.Музыки** - доступ к вашим плейлистам  
- 🎵 **Скачивание треков** в высоком качестве (MP3 192kbps)
- 📱 **Интерактивное меню** с навигацией
- 🔐 **Технические аккаунты** - безопасная работа без личных данных

## 🚀 Быстрый старт

### 1. Клонирование репозитория
```bash
git clone https://github.com/your-username/music-telegram-bot.git
cd music-telegram-bot
```

### 2. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 3. Настройка переменных окружения
Скопируйте `.env.example` в `.env` и заполните:
```bash
cp .env.example .env
```

Отредактируйте `.env`:
```env
BOT_TOKEN=your_telegram_bot_token
VK_ACCESS_TOKEN=your_vk_token
YANDEX_TOKEN=your_yandex_token
```

### 4. Установка FFmpeg
**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**Windows:**
1. Скачайте с https://ffmpeg.org/download.html
2. Добавьте в PATH

**macOS:**
```bash
brew install ffmpeg
```

### 5. Запуск
```bash
python music_bot.py
```

## 🔑 Получение токенов

### Telegram Bot Token
1. Найдите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Получите токен

### VK Access Token
1. Перейдите на https://vk.com/apps?act=manage
2. Создайте Standalone приложение
3. Получите токен через OAuth:
```
https://oauth.vk.com/authorize?client_id=CLIENT_ID&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=audio&response_type=token&v=5.131
```

### Yandex Music Token
1. Зайдите на https://oauth.yandex.ru/
2. Создайте приложение
3. Получите токен с правами на музыку

## 🐳 Docker развертывание

### Сборка и запуск
```bash
docker-compose up -d --build
```

### Только сборка
```bash
docker build -t music-bot .
```

### Запуск контейнера
```bash
docker run -d --name music-bot \
  -e BOT_TOKEN=your_token \
  -e VK_ACCESS_TOKEN=your_vk_token \
  -e YANDEX_TOKEN=your_yandex_token \
  music-bot
```

## 🌐 Деплой на облачные платформы

### Railway.app
1. Подключите GitHub репозиторий
2. Добавьте переменные окружения в настройках
3. Railway автоматически деплоит при push

### Render.com
1. Создайте Web Service из GitHub
2. Добавьте переменные окружения
3. Используйте команду запуска: `python music_bot.py`

### Heroku
```bash
heroku create your-music-bot
heroku config:set BOT_TOKEN=your_token
heroku config:set VK_ACCESS_TOKEN=your_vk_token
heroku config:set YANDEX_TOKEN=your_yandex_token
git push heroku main
```

## 📋 Структура проекта

```
music-telegram-bot/
├── music_bot.py          # Основной код бота
├── requirements.txt      # Python зависимости
├── .env.example         # Пример конфигурации
├── Dockerfile           # Docker конфигурация
├── docker-compose.yml   # Docker Compose
├── railway.json         # Railway деплой
├── Procfile            # Heroku деплой
├── README.md           # Документация
└── .gitignore          # Git игнор файл
```

## ⚙️ Конфигурация

### Переменные окружения
| Переменная | Описание | Обязательная |
|------------|----------|--------------|
| `BOT_TOKEN` | Токен Telegram бота | ✅ |
| `VK_ACCESS_TOKEN` | Токен ВКонтакте API | ❌ |
| `YANDEX_TOKEN` | Токен Яндекс.Музыки | ❌ |
| `MAX_FILE_SIZE_MB` | Максимальный размер файла (MB) | ❌ |
| `MAX_DURATION_SECONDS` | Максимальная длительность (сек) | ❌ |

### Ограничения
- **Размер файла:** до 50MB (лимит Telegram)
- **Длительность:** до 10 минут
- **Качество аудио:** MP3 192kbps
- **Источники:** YouTube, ВКонтакте, Яндекс.Музыка

## 🔧 Разработка

### Запуск в режиме разработки
```bash
python -m pip install -r requirements.txt
python music_bot.py
```

### Логирование
Логи сохраняются в консоль с уровнем INFO. Для отладки измените:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Тестирование
```bash
# Проверка импортов
python -c "import music_bot; print('OK')"

# Проверка FFmpeg
ffmpeg -version
```

## 📊 Мониторинг

### Статус сервисов
Бот проверяет доступность сервисов при запуске:
- ✅ VK service initialized  
- ✅ Yandex Music service initialized

### Логи ошибок
```bash
# Просмотр логов Docker
docker logs music-bot -f

# Просмотр логов Railway
railway logs

# Просмотр логов Heroku
heroku logs -t -a your-app-name
```

## 🤝 Поддержка

### Часто задаваемые вопросы

**Q: Бот не отвечает**  
A: Проверьте правильность `BOT_TOKEN` и доступность сервера

**Q: Не работает ВК**  
A: Убедитесь в правильности `VK_ACCESS_TOKEN` и правах доступа

**Q: Ошибка FFmpeg**  
A: Установите FFmpeg в систему или контейнер

**Q: Файлы слишком большие**  
A: Уменьшите качество аудио или лимит длительности

### Контакты
- GitHub Issues: [Создать issue](https://github.com/your-username/music-telegram-bot/issues)
- Telegram: @your_username

## 📄 Лицензия

MIT License - см. файл [LICENSE](LICENSE)

## ⚠️ Дисклеймер

Бот создан для образовательных целей. Соблюдайте авторские права и условия использования музыкальных сервисов.