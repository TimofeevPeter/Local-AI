from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import os
import shutil
from typing import Optional

from database import init_db, get_history, save_message, clear_history
from bot_engine import get_response, analyze_image

# ===== НАСТРОЙКИ =====
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===== ИНИЦИАЛИЗАЦИЯ =====
app = FastAPI(title="FoxBot API")

# Разрешаем CORS (чтобы веб-интерфейс мог обращаться)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== МОДЕЛИ ДАННЫХ =====
class MessageRequest(BaseModel):
    text: str

class MessageResponse(BaseModel):
    success: bool
    text: str = ""
    audio: str = None
    error: str = None

class UploadResponse(BaseModel):
    success: bool
    text: str = ""
    audio: str = None
    description: str = ""
    error: str = None

# ===== ИНИЦИАЛИЗАЦИЯ ПРИ ЗАПУСКЕ =====
@app.on_event("startup")
async def startup():
    init_db()
    print("Сервер запущен!")
    print(f"📁 Папка загрузок: {os.path.abspath(UPLOAD_FOLDER)}")

# ===== API ENDPOINTS =====

@app.get("/")
async def root():
    """Проверка работы сервера"""
    return {"status": "online", "bot": "Лисёнок готов!"}

@app.get("/history")
async def get_message_history(limit: int = 50):
    """Получить историю переписки"""
    return {"messages": get_history(limit)}

@app.post("/message", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """Отправить сообщение боту (текст)"""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Пустое сообщение")
    
    result = await get_response(request.text)
    
    if result["success"]:
        return MessageResponse(
            success=True,
            text=result["text"],
            audio=result["audio"]
        )
    else:
        raise HTTPException(status_code=500, detail=result["error"])

@app.post("/upload", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    text: Optional[str] = Form("")
):
    """Загрузить изображение и получить описание"""
    try:
        # Проверяем тип файла
        allowed_extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp"]
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            return UploadResponse(
                success=False,
                error=f"Неподдерживаемый формат. Разрешены: {', '.join(allowed_extensions)}"
            )
        
        # Сохраняем файл
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"📷 Получено изображение: {file.filename}")
        
        # Анализируем изображение
        print("👁️ Анализирую изображение...")
        description = await analyze_image(filepath)
        print(f"📝 Описание: {description}")
        
        # Формируем запрос боту
        if text:
            full_text = f"{text}\n\n[Изображение: {description}]"
        else:
            full_text = f"[Изображение: {description}]"
        
        # Получаем ответ от бота
        result = await get_response(full_text)
        
        if result["success"]:
            return UploadResponse(
                success=True,
                text=result["text"],
                audio=result["audio"],
                description=description
            )
        else:
            return UploadResponse(
                success=True,  # Картинка обработана, но бот ошибся
                text=result.get("text", "Не удалось получить ответ"),
                audio=result.get("audio"),
                description=description
            )
            
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return UploadResponse(
            success=False,
            error=str(e)
        )

@app.post("/clear")
async def clear_chat():
    """Очистить историю"""
    clear_history()
    return {"success": True, "message": "История очищена"}

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Получить аудиофайл"""
    filepath = os.path.join("cache", filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    raise HTTPException(status_code=404, detail="Аудио не найдено")

@app.get("/image/{filename}")
async def get_image(filename: str):
    """Получить изображение"""
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    raise HTTPException(status_code=404, detail="Изображение не найдено")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        reload=True
    )
