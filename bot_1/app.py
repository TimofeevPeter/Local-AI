import customtkinter as ctk
import requests
import pygame
import os
import threading
import base64
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from datetime import datetime

# ===== НАСТРОЙКИ =====
API_URL = "http://127.0.0.1:5000"
VOICE_CACHE = "../cache"
UPLOAD_FOLDER = "../uploads"

# Настройка темы
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Инициализация звука
pygame.mixer.init()

class FoxBotApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Настройки окна
        self.title("🦊 Лисёнок")
        self.geometry("500x700")
        self.minsize(400, 600)
        
        # Состояние
        self.is_loading = False
        self.selected_image = None
        
        # Создаём интерфейс
        self.create_widgets()
        
        # Загружаем историю
        self.load_history()
        
    def create_widgets(self):
        # Заголовок
        self.header = ctk.CTkLabel(
            self, 
            text="🦊 Лисёнок", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.header.pack(pady=10)
        
        # Окно чата
        self.chat_frame = ctk.CTkScrollableFrame(self, label_text="Чат")
        self.chat_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Поле ввода
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(pady=10, padx=10, fill="x")
        
        # Кнопка прикрепления
        self.attach_btn = ctk.CTkButton(
            self.input_frame, 
            text="📎", 
            width=50,
            command=self.attach_image
        )
        self.attach_btn.pack(side="left", padx=(0, 10))
        
        # Поле ввода текста
        self.message_entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Введите сообщение...",
            font=ctk.CTkFont(size=14)
        )
        self.message_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.message_entry.bind("<Return>", lambda e: self.send_message())
        
        # Кнопка отправки
        self.send_btn = ctk.CTkButton(
            self.input_frame, 
            text="➤", 
            width=50,
            command=self.send_message
        )
        self.send_btn.pack(side="right")
        
        # Индикатор загрузки
        self.loading_label = ctk.CTkLabel(
            self, 
            text="", 
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.loading_label.pack(pady=5)
        
        # Кнопка очистки
        self.clear_btn = ctk.CTkButton(
            self, 
            text="🗑️ Очистить историю", 
            width=150,
            command=self.clear_chat,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90")
        )
        self.clear_btn.pack(pady=5)
        
        # Метка для выбранной картинки
        self.image_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="green"
        )
        self.image_label.pack(pady=2)
        
    def attach_image(self):
        """Выбор изображения"""
        filepath = filedialog.askopenfilename(
            title="Выберите изображение",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.webp"),
                ("All files", "*.*")
            ]
        )
        if filepath:
            self.selected_image = filepath
            filename = os.path.basename(filepath)
            self.image_label.configure(text=f"📎 Выбрано: {filename}")
            
    def add_message(self, role, content):
        """Добавляет сообщение в чат"""
        bubble = ctk.CTkFrame(
            self.chat_frame, 
            fg_color=("gray75", "gray25") if role == "user" else ("#667eea", "#556ee6"),
            corner_radius=15
        )
        bubble.pack(fill="x", pady=5, padx=10, anchor="e" if role == "user" else "w")
        
        label = ctk.CTkLabel(
            bubble, 
            text=content, 
            font=ctk.CTkFont(size=13),
            justify="left",
            wraplength=350,
            text_color=("black", "white") if role == "user" else ("white", "white")
        )
        label.pack(padx=12, pady=8)
        
        # Прокрутка вниз
        try:
            self.chat_frame._scrollbar.set(1.0, 1.0)
        except:
            pass
            
    def load_history(self):
        """Загружает историю из API"""
        try:
            response = requests.get(f"{API_URL}/history", timeout=5)
            if response.status_code == 200:
                data = response.json()
                for msg in data.get("messages", []):
                    role = "user" if msg["role"] == "user" else "bot"
                    self.add_message(role, msg["content"])
        except:
            self.add_message("system", "⚠️ Не удалось загрузить историю")
            
    def send_message(self):
        """Отправляет сообщение"""
        text = self.message_entry.get().strip()
        
        if not text and not self.selected_image:
            return
            
        if self.is_loading:
            return
        
        # Добавляем сообщение пользователя
        if text:
            self.add_message("user", text)
        if self.selected_image:
            filename = os.path.basename(self.selected_image)
            self.add_message("user", f"[📎 Картинка: {filename}]")
        
        self.message_entry.delete(0, "end")
        
        # Показываем загрузку
        self.is_loading = True
        self.loading_label.configure(text="🦊 Лисёнок думает...")
        self.send_btn.configure(state="disabled")
        self.attach_btn.configure(state="disabled")
        
        # Запускаем в отдельном потоке
        if self.selected_image:
            thread = threading.Thread(
                target=self._upload_image, 
                args=(text, self.selected_image), 
                daemon=True
            )
        else:
            thread = threading.Thread(
                target=self._api_request, 
                args=(text,), 
                daemon=True
            )
        
        thread.start()
        
    def _api_request(self, user_text):
        """Запрос к API (текст)"""
        try:
            response = requests.post(
                f"{API_URL}/message",
                json={"text": user_text},
                timeout=180
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["success"]:
                    self.after(0, lambda: self.add_message("bot", data["text"]))
                    if data.get("audio"):
                        self.after(0, lambda: self.play_audio(data["audio"]))
                else:
                    self.after(0, lambda: self.add_message("system", f"⚠️ {data['error']}"))
            else:
                self.after(0, lambda: self.add_message("system", f"⚠️ Ошибка {response.status_code}"))
                
        except Exception as e:
            self.after(0, lambda: self.add_message("system", f"⚠️ {str(e)}"))
            
        finally:
            self.after(0, self._reset_ui)
            
    def _upload_image(self, text, image_path):
        """Загрузка изображения"""
        try:
            with open(image_path, "rb") as img:
                files = {"file": (os.path.basename(image_path), img)}
                data = {"text": text}
                
                response = requests.post(
                    f"{API_URL}/upload",
                    files=files,
                    data=data,
                    timeout=180
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result["success"]:
                        self.after(0, lambda: self.add_message("bot", result["text"]))
                        if result.get("audio"):
                            self.after(0, lambda: self.play_audio(result["audio"]))
                    else:
                        self.after(0, lambda: self.add_message("system", f"⚠️ {result['error']}"))
                else:
                    self.after(0, lambda: self.add_message("system", f"⚠️ Ошибка {response.status_code}"))
                    
        except Exception as e:
            self.after(0, lambda: self.add_message("system", f"⚠️ {str(e)}"))
            
        finally:
            self.after(0, self._reset_ui)
            
    def _reset_ui(self):
        """Сброс UI"""
        self.is_loading = False
        self.loading_label.configure(text="")
        self.send_btn.configure(state="normal")
        self.attach_btn.configure(state="normal")
        self.selected_image = None
        self.image_label.configure(text="")
        
    def play_audio(self, audio_path):
        """Воспроизводит аудио"""
        try:
            filename = audio_path.replace('cache\\', '').replace('cache/', '')
            filepath = os.path.join(VOICE_CACHE, filename)
            
            if os.path.exists(filepath):
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
        except Exception as e:
            print(f"⚠️ Ошибка аудио: {e}")
            
    def clear_chat(self):
        """Очищает чат"""
        if messagebox.askyesno("Подтверждение", "Удалить всю историю переписки?"):
            try:
                requests.post(f"{API_URL}/clear", timeout=5)
                # Очищаем интерфейс
                for widget in self.chat_frame.winfo_children():
                    widget.destroy()
                self.add_message("system", "🗑️ История очищена")
            except:
                self.add_message("system", "⚠️ Не удалось очистить")
                
    def run(self):
        """Запуск приложения"""
        self.mainloop()

# ===== ЗАПУСК =====
if __name__ == "__main__":
    app = FoxBotApp()
    app.run()
