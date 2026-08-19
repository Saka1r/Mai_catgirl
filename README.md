# 🐱 Mai Userbot

Ленивая кошечка-собеседница в Telegram на базе локальной LLM (llama.cpp вы можете использовать ollama и т.д). 

## ✨ Возможности

- 💬 Живое общение в ЛС и группах
- 🧠 Долгосрочная память (чаты, пользователи, глобальные факты)
- 😴 Симуляция сна (не читает сообщения ночью)
- 🛡 Модерация токсичных сообщений (LLM + keyword-фильтр)
- 📝 Дневник мыслей и эмоций
- 🚀 Проактивные сообщения (пишет первая, когда скучно)
- 🔐 Разграничение доступа к памяти (создатель vs обычные)

## 🚀 Быстрый старт

### 1. Зависимости

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 2. Конфигурация
``` bash
cp .env.example .env
# Отредактируй .env: API_ID, API_HASH, CREATOR_USER_ID
```

### 3. Запуск LLM
```bash
llama-server -m qwen2.5-14b-instruct-q4_k_m.gguf -c 8192 -ngl 99 --port 8080
# or
llama-server -m qwen2.5-14b-instruct-q4_k_m.gguf -c 16384 -ngl 99 --port 8080
# or llama3-8B | I do not recommend
```

### 4. Запуск
```bash
python main.py
```

### 📄 Лицензия MIT
