import requests
import asyncio
import edge_tts
import os
import hashlib
import base64
import json
import random
from datetime import datetime
from database import save_message, get_history

# ===== НАСТРОЙКИ =====
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
VOICE = "ru-RU-SvetlanaNeural"
CACHE_FOLDER = "cache"
MAX_HISTORY = 50
FACTS_FILE = "user_facts.json"

os.makedirs(CACHE_FOLDER, exist_ok=True)

# ===== ФАКТЫ О ПОЛЬЗОВАТЕЛЕ =====
DEFAULT_FACTS = {
    "name": "Пользователь",
    "interests": ["программирование", "игры", "аниме"],
    "favorite_character": "Мику",
    "timezone": "MSK",
    "favorite_color": "синий",
    "pet": "нет",
}

def load_facts():
    """Загружает факты из файла"""
    if os.path.exists(FACTS_FILE):
        try:
            with open(FACTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return DEFAULT_FACTS.copy()
    return DEFAULT_FACTS.copy()

def save_facts(facts):
    """Сохраняет факты в файл"""
    with open(FACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)

def update_facts_from_message(message: str, facts: dict) -> dict:
    """Анализирует сообщение и обновляет факты (упрощённая версия)"""
    text = message.lower()
    
    # Простые правила для извлечения фактов
    if "меня зовут" in text or "моё имя" in text:
        # Здесь можно добавить парсинг имени
        pass
    
    if "мику" in text and "favorite_character" not in facts.get("interests", []):
        facts["favorite_character"] = "Мику"
    
    if "python" in text and "программирование" not in facts.get("interests", []):
        if "interests" not in facts:
            facts["interests"] = []
        facts["interests"].append("программирование")
    
    save_facts(facts)
    return facts

# ===== КЭШ =====
def get_cache_filename(text: str, mood: str = "calm") -> str:
    return os.path.join(
        CACHE_FOLDER, 
        hashlib.md5(f"{text}_{mood}".encode()).hexdigest() + ".mp3"
    )

# ===== ОЗВУЧКА =====
async def speak(text: str, mood: str = "calm") -> str:
    """Генерирует аудио, возвращает путь к файлу"""
    voice_settings = {
        "happy": {"rate": "+5%", "pitch": "+5Hz"},
        "calm": {"rate": "+0%", "pitch": "+0Hz"},
        "sad": {"rate": "-10%", "pitch": "-5Hz"},
    }
    
    cfg = voice_settings.get(mood, voice_settings["calm"])
    path = get_cache_filename(text, mood)
    
    try:
        if not os.path.exists(path):
            print(f"🔊 Генерация голоса...")
            c = edge_tts.Communicate(text, VOICE, rate=cfg["rate"], pitch=cfg["pitch"])
            await c.save(path)
        
        return path
    except Exception as e:
        print(f"⚠️ Ошибка озвучки: {e}")
        return None

# ===== АНАЛИЗ ИЗОБРАЖЕНИЯ (LM Studio) =====
async def analyze_image(image_path: str) -> str:
    """Анализирует изображение через LM Studio"""
    try:
        print(f"Анализ изображения: {image_path}")
        print(f"Полный путь: {os.path.abspath(image_path)}")
        
        if not os.path.exists(image_path):
            return f"Файл не найден: {image_path}"
        
        with open(image_path, "rb") as img:
            img_data = base64.b64encode(img.read()).decode()
        
        print(f"📤 Отправляю в LM Studio...")
        
        try:
            health = requests.get("http://127.0.0.1:1234/health", timeout=5)
            print(f"✅ LM Studio отвечает: {health.status_code}")
        except:
            return "❌ LM Studio не отвечает на порту 1234"
        
        response = requests.post(
            LM_STUDIO_URL,
            json={
                "model": "bakllava",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Опиши кратко что ты видишь на этом изображении (1-2 предложения). Отвечай на русском языке."},
                            {"type": "image_url", "image_url": {"url": f"image/jpeg;base64,{img_data}"}}
                        ]
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7
            },
            timeout=300
        )
        
        print(f"Ответ от LM Studio: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()['choices'][0]['message']['content']
            print(f"Результат анализа: {result}")
            return result
        else:
            return f"Ошибка LM Studio: {response.status_code}"
        
    except requests.exceptions.Timeout:
        return "⏱Превышено время ожидания от LM Studio"
    except requests.exceptions.ConnectionError:
        return "❌ Не удалось подключиться к LM Studio"
    except Exception as e:
        error_msg = f"Ошибка анализа: {e}"
        print(f"❌ {error_msg}")
        return error_msg

# ===== НАСТРОЕНИЕ =====
def get_mood(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ['рад', 'класс', 'круто', '!', 'хаха']):
        return "happy"
    if any(w in t for w in ['груст', 'плохо', 'устал']):
        return "sad"
    return "calm"

# ===== КОНТЕКСТНЫЕ ЯКОРЯ =====
def extract_context_anchor(messages: list) -> str:
    """Ищет интересные факты в истории для упоминания"""
    recent = messages[-20:]  # Смотрим последние 20 сообщений
    
    topics = {
        "игры": ["osu", "metro", "игра", "проходил", "steam", "gaming"],
        "мику": ["мику", "miku", "хацунэ", "песня", "вокалоид"],
        "код": ["код", "python", "ошибка", "запустил", "сервер", "api"],
        "аниме": ["аниме", "сериал", "манга", "наруто", "ван пис"],
        "работа": ["работа", "учеба", "проект", "задача", "дедлайн"],
    }
    
    found_topics = []
    for topic, keywords in topics.items():
        for msg in recent:
            if msg["role"] == "user" and any(kw in msg["content"].lower() for kw in keywords):
                if topic not in found_topics:
                    found_topics.append(topic)
                break
    
    if found_topics:
        return f"(Пользователь недавно упоминал: {', '.join(found_topics)})"
    
    return ""

# ===== ОТВЕТ БОТА =====
async def get_response(user_text: str) -> dict:
    """Генерирует ответ бота"""
    
    # Загружаем факты
    facts = load_facts()
    
    # Обновляем факты на основе сообщения
    facts = update_facts_from_message(user_text, facts)
    
    # Сохраняем сообщение пользователя
    save_message("user", user_text)
    
    # Загружаем историю
    messages = get_history(MAX_HISTORY)
    
    # Системный промпт
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        greeting = "Доброе утро!"
    elif 12 <= hour < 17:
        greeting = "Добрый день!"
    elif 17 <= hour < 23:
        greeting = "Добрый вечер!"
    else:
        greeting = "Доброй ночи!"
    
    # Формируем блок фактов
    facts_text = "\n".join([f"- {k}: {v}" if not isinstance(v, list) else f"- {k}: {', '.join(v)}" for k, v in facts.items()])
    
    # Контекстный якорь
    anchor = extract_context_anchor(messages)
    anchor_text = f"\n🔗 {anchor}" if anchor else ""
    
    system = f"""Ты Лисёнок — дружелюбный ИИ-компаньон.
{greeting}

О пользователе:
{facts_text}{anchor_text}

Отвечай кратко (2-3 предложения), неформально.
Отвечай ТОЛЬКО на русском языке!
Проявляй интерес к пользователю, задавай вопросы иногда. Но не более одного вопроса в сообщении"""
    
    # Формируем контекст
    context = [{"role": "system", "content": system}]
    context.extend([{"role": m["role"], "content": m["content"]} for m in messages[-MAX_HISTORY:]])
    
    # Запрос к LM Studio
    try:
        r = requests.post(
            LM_STUDIO_URL,
            json={"messages": context, "temperature": 0.7, "max_tokens": 500},
            timeout=180
        )
        
        if r.status_code == 200:
            ai_text = r.json()['choices'][0]['message']['content']
            
            # Проверка на китайский
            if any('\u4e00' <= char <= '\u9fff' for char in ai_text):
                print("⚠️ Китайский язык! Запрашиваю русский...")
            
            # Добавляем проактивность
            ai_text = add_proactive_element(ai_text, user_text)
            
            save_message("assistant", ai_text)
            
            # Генерируем аудио
            audio_path = await speak(ai_text, get_mood(ai_text))
            
            return {
                "success": True,
                "text": ai_text,
                "audio": audio_path,
                "mood": get_mood(ai_text)
            }
        else:
            return {"success": False, "error": f"HTTP {r.status_code}"}
            
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Превышено время ожидания"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "LM Studio не отвечает"}
    except Exception as e:
        return {"success": False, "error": str(e)}
