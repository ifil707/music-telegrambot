# Создам полный набор файлов для развертывания музыкального бота

# 1. requirements.txt
requirements_content = """aiogram==3.7.0
aiohttp==3.9.0
aiofiles==23.2.0
yt-dlp==2024.8.6
vk-api==11.9.9
yandex-music==2.1.1
python-dotenv==1.0.0
ffmpeg-python==0.2.0
pathlib
asyncio
logging
"""

# 2. .env файл с примером конфигурации
env_content = """# Telegram Bot Token (получить у @BotFather)
BOT_TOKEN=your_telegram_bot_token_here

# VK Access Token (токен приложения ВКонтакте)
VK_ACCESS_TOKEN=your_vk_access_token_here

# Yandex Music Token (OAuth токен Яндекс.Музыки)
YANDEX_TOKEN=your_yandex_music_token_here

# Настройки ограничений
MAX_FILE_SIZE_MB=50
MAX_DURATION_SECONDS=600
"""

# 3. Dockerfile для контейнеризации
dockerfile_content = """FROM python:3.9-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \\
    ffmpeg \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование и установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Создание директории для временных файлов
RUN mkdir -p /tmp/music_bot

# Экспорт порта (если нужен для healthcheck)
EXPOSE 8080

# Запуск бота
CMD ["python", "music_bot.py"]
"""

# 4. docker-compose.yml
docker_compose_content = """version: '3.8'

services:
  music-bot:
    build: .
    container_name: music-telegram-bot
    restart: unless-stopped
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - VK_ACCESS_TOKEN=${VK_ACCESS_TOKEN}
      - YANDEX_TOKEN=${YANDEX_TOKEN}
    volumes:
      - ./temp:/tmp/music_bot
      - ./logs:/app/logs
    networks:
      - music-bot-network

networks:
  music-bot-network:
    driver: bridge
"""

# 5. Railway deployment файл
railway_content = """{
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "startCommand": "python music_bot.py",
    "restartPolicyType": "always",
    "replicas": 1
  }
}"""

# 6. Procfile for Heroku
procfile_content = """web: python music_bot.py"""

# 7. .gitignore
gitignore_content = """.env
.env.local
.env.production
*.log
logs/
temp/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
.coverage
htmlcov/
.pytest_cache/
.vscode/
.idea/
*.mp3
*.m4a
*.webm
*.mp4
node_modules/
"""

# 8. README.md с инструкциями
readme_content = """# 🎵 Музыкальный Telegram Бот

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
docker run -d --name music-bot \\
  -e BOT_TOKEN=your_token \\
  -e VK_ACCESS_TOKEN=your_vk_token \\
  -e YANDEX_TOKEN=your_yandex_token \\
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
"""

# 9. GitHub Actions для CI/CD
github_actions_content = """name: Deploy Music Bot

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python 3.9
      uses: actions/setup-python@v4
      with:
        python-version: 3.9
    
    - name: Install FFmpeg
      run: |
        sudo apt-get update
        sudo apt-get install -y ffmpeg
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Test imports
      run: |
        python -c "
        import asyncio
        import yt_dlp
        import vk_api
        import yandex_music
        from aiogram import Bot, Dispatcher
        print('All imports successful')
        "
    
    - name: Check FFmpeg
      run: ffmpeg -version
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to Railway
      run: |
        echo "Deploying to Railway..."
        # Railway деплоится автоматически при push
"""

# 10. Сохранение всех файлов
files_to_create = {
    'requirements.txt': requirements_content,
    '.env.example': env_content,
    'Dockerfile': dockerfile_content,
    'docker-compose.yml': docker_compose_content,
    'railway.json': railway_content,
    'Procfile': procfile_content,
    '.gitignore': gitignore_content,
    'README.md': readme_content,
    '.github/workflows/deploy.yml': github_actions_content
}

# Создаем все файлы
for filename, content in files_to_create.items():
    # Создаем директории если нужно
    if '/' in filename:
        directory = '/'.join(filename.split('/')[:-1])
        import os
        os.makedirs(directory, exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content.strip())

print("✅ Созданы все файлы проекта:")
for filename in files_to_create.keys():
    print(f"  📄 {filename}")

print("\n🚀 Структура проекта готова!")
print("📋 Следующие шаги:")
print("1. Сохранить основной код в music_bot.py")
print("2. Скопировать .env.example в .env")
print("3. Заполнить токены в .env файле")
print("4. Установить зависимости: pip install -r requirements.txt")
print("5. Запустить бота: python music_bot.py")
print("\n🌐 Для деплоя:")
print("- Railway: push в GitHub репозиторий")
print("- Docker: docker-compose up -d --build")
print("- Heroku: следовать инструкциям в README.md")