import hashlib, time, threading, requests, json
import customtkinter as ctk
from tkinter import messagebox

# --- НАСТРОЙКИ ---
# Вставь свою ссылку из Firebase Console (Realtime Database)
BASE_URL = "https://firebaseio.com"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SimpleMessenger(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TG Clone (No E2EE)")
        self.geometry("450x700")
        
        self.current_user = None
        self.target_user = "GLOBAL" 
        self.last_id = None

        self.setup_ui()

    def setup_ui(self):
        # Экран входа
        self.auth_frame = ctk.CTkFrame(self)
        self.auth_frame.pack(pady=50, padx=40, fill="both", expand=True)
        ctk.CTkLabel(self.auth_frame, text="Вход в чат", font=("Arial", 20, "bold")).pack(pady=20)
        
        self.n_entry = ctk.CTkEntry(self.auth_frame, placeholder_text="@nickname")
        self.n_entry.pack(pady=10, fill="x", padx=30)
        self.p_entry = ctk.CTkEntry(self.auth_frame, placeholder_text="пароль", show="*")
        self.p_entry.pack(pady=10, fill="x", padx=30)
        ctk.CTkButton(self.auth_frame, text="Войти / Регистрация", command=self.auth).pack(pady=20)

        # Главный экран чата
        self.chat_frame = ctk.CTkFrame(self)
        
        # Навигация (Общий / ЛС)
        self.nav_bar = ctk.CTkFrame(self.chat_frame)
        self.nav_bar.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(self.nav_bar, text="ОБЩИЙ ЧАТ", width=100, command=lambda: self.switch_chat("GLOBAL")).pack(side="left", padx=5)
        self.target_entry = ctk.CTkEntry(self.nav_bar, placeholder_text="Кому (@nick)?")
        self.target_entry.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(self.nav_bar, text="Найти", width=60, command=self.open_private).pack(side="right", padx=5)

        self.display = ctk.CTkTextbox(self.chat_frame, state="disabled", fg_color="#17212B", font=("Arial", 14))
        self.display.pack(padx=10, pady=10, fill="both", expand=True)

        self.msg_entry = ctk.CTkEntry(self.chat_frame, placeholder_text="Введите сообщение...")
        self.msg_entry.pack(fill="x", padx=10, pady=10)
        self.msg_entry.bind("<Return>", lambda e: self.send())

    def auth(self):
        nick = self.n_entry.get().strip().lower()
        pw = self.p_entry.get().strip()
        if not nick.startswith("@") or len(nick) < 3: 
            messagebox.showerror("Ошибка", "Ник должен начинаться с @")
            return

        clean_nick = nick.replace("@", "")
        pw_hash = hashlib.sha256(pw.encode()).hexdigest()

        try:
            # Проверка / Регистрация
            res = requests.get(f"{BASE_URL}users/{clean_nick}.json").json()
            if res:
                if res['pw'] != pw_hash:
                    messagebox.showerror("Ошибка", "Неверный пароль")
                    return
            else:
                requests.put(f"{BASE_URL}users/{clean_nick}.json", json={"pw": pw_hash})
            
            self.current_user = nick
            self.auth_frame.pack_forget()
            self.chat_frame.pack(fill="both", expand=True)
            self.switch_chat("GLOBAL")
        except Exception as e:
            messagebox.showerror("Ошибка сети", f"Проверь подключение!\n{e}")

    def open_private(self):
        target = self.target_entry.get().strip().lower()
        if not target.startswith("@"):
            messagebox.showwarning("Внимание", "Введите ник с @")
            return
        
        # ПРОВЕРКА: Существует ли такой пользователь в базе?
        clean_target = target.replace("@", "")
        try:
            res = requests.get(f"{BASE_URL}users/{clean_target}.json").json()
            if res:
                self.switch_chat(target)
            else:
                messagebox.showerror("Ошибка", f"Пользователь {target} не зарегистрирован!")
        except:
            messagebox.showerror("Ошибка", "Не удалось проверить пользователя")

    def switch_chat(self, target):
        self.target_user = target
        self.last_id = None # Сбрасываем ID, чтобы загрузить историю нового чата
        self.display.configure(state="normal")
        self.display.delete("1.0", "end")
        self.display.insert("end", f"--- Чат: {target} ---\n")
        self.display.configure(state="disabled")
        
        # Запускаем фоновый поток получения сообщений
        threading.Thread(target=self.receive, daemon=True).start()

    def send(self):
        txt = self.msg_entry.get().strip()
        if not txt: return
        
        # Логика путей в Firebase
        if self.target_user == "GLOBAL":
            path = "public_chat"
        else:
            # ID чата всегда одинаковый для двух людей (сортировка ников)
            chat_id = "_".join(sorted([self.current_user.replace("@",""), self.target_user.replace("@","")]))
            path = f"chats/{chat_id}"
            
        try:
            requests.post(f"{BASE_URL}{path}.json", json={
                "from": self.current_user, 
                "msg": txt, 
                "time": time.time()
            })
            self.msg_entry.delete(0, "end")
        except:
            messagebox.showerror("Ошибка", "Не удалось отправить")

    def receive(self):
        my_target = self.target_user # Чтобы поток понимал, в каком он чате
        while self.target_user == my_target:
            try:
                if self.target_user == "GLOBAL":
                    path = "public_chat"
                else:
                    chat_id = "_".join(sorted([self.current_user.replace('@',''), self.target_user.replace('@','')]))
                    path = f"chats/{chat_id}"
                
                r = requests.get(f"{BASE_URL}{path}.json").json()
                if r:
                    for mid in r:
                        if self.last_id is None or mid > self.last_id:
                            msg_data = r[mid]
                            self.show_msg(msg_data['from'], msg_data['msg'])
                            self.last_id = mid
            except: 
                pass
            time.sleep(1)

    def show_msg(self, user, text):
        self.display.configure(state="normal")
        # Выделяем свои сообщения цветом (опционально)
        prefix = "Вы" if user == self.current_user else user
        self.display.insert("end", f"{prefix}: {text}\n")
        self.display.configure(state="disabled")
        self.display.see("end")

if __name__ == "__main__":
    app = SimpleMessenger()
    app.mainloop()
