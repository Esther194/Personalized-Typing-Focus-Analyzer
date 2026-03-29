import keyboard
import time
import sys
import mysql.connector
import numpy as np
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import os
from dotenv import load_dotenv

#全域變數
A = [[], []]  # 輸入值跟時間
b = 0  # backspace計數
current_user_id = None
is_monitoring = False

# 讀取.env 檔案
load_dotenv()

#資料庫函數
def get_db_connection():
    #建立資料庫連接
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),      # 讀取 .env 裡的 DB_HOST
            user=os.getenv("DB_USER"),      # 讀取 .env 裡的 DB_USER
            password=os.getenv("DB_PASSWORD"), # 讀取 .env 裡的 DB_PASSWORD
            database=os.getenv("DB_NAME"), # 讀取 .env 裡的 DB_NAME
        )
        return conn
    except mysql.connector.Error as err:
        print(f"資料庫連接失敗: {err}")
        return None


def sign_up(account, password):
    #註冊
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (account, password) VALUES (%s, %s)",
            (account, password)
        )
        conn.commit()
        return True, "註冊成功！"
    except mysql.connector.IntegrityError:
        return False, "帳號已存在"
    except mysql.connector.Error as err:
        return False, f"註冊失敗: {err}"
    finally:
        cursor.close()
        conn.close()

def login(account, password):
    #登入並返回 user_id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id FROM users WHERE account = %s AND password = %s",
        (account, password)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        return result[0], "登入成功"
    else:
        return None, "帳號或密碼錯誤"

def save_focus_record(user_id, focus_score, wpm, iki_mean, iki_std, bsr, total_keys, duration):
    #儲存專注度記錄
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO focus_records 
            (user_id, focus_score, wpm, iki_mean, iki_std, bsr, total_keys, session_duration)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (user_id, focus_score, wpm, iki_mean, iki_std, bsr, total_keys, duration))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"儲存失敗: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

#按鍵處理
def on_key(event):
    global b, is_monitoring
    if not is_monitoring:
        return
    
    A[0].append(event.name)
    A[1].append(time.time())
    
    if event.name == 'backspace':
        b += 1

def keys_to_string(keys):
    #將按鍵序列轉換為文字
    result = ""
    for key in keys:
        if key == 'backspace':
            if result:
                result = result[:-1]
        elif key == 'enter':
            result += '\n'
        elif key == 'space':
            result += ' '
        elif key == 'tab':
            result += '\t'
        elif len(key) == 1:
            result += key
    return result

#分析函數
def calculate_iki_stats(timestamps):
    #計算鍵間時間統計
    if len(timestamps) < 2:
        return {'mean': 0, 'std': 0}
    
    iki_times = []
    for i in range(1, len(timestamps)):
        iki = (timestamps[i] - timestamps[i-1]) * 1000
        if iki < 2000:
            iki_times.append(iki)
    
    if not iki_times:
        return {'mean': 0, 'std': 0}
    
    return {
        'mean': np.mean(iki_times),
        'std': np.std(iki_times)
    }

def calculate_focus_index(keys, timestamps, backspace_count):
    #計算專注指數 (0-100分)
    if len(timestamps) < 2:
        return 0, {}, {}
    
    total_time = timestamps[-1] - timestamps[0]
    typing_speed = (len(keys) / total_time) * 60 if total_time > 0 else 0
    iki_stats = calculate_iki_stats(timestamps)
    backspace_rate = (backspace_count / len(keys)) * 100 if keys else 0
    
    # 評分
    speed_score = min(30, (typing_speed / 60) * 30)
    consistency_score = max(0, 30 - (iki_stats['std'] / 100) * 30)
    error_score = max(0, 40 - backspace_rate * 2)
    focus_index = speed_score + consistency_score + error_score
    
    details = {
        'speed_score': speed_score,
        'consistency_score': consistency_score,
        'error_score': error_score,
        'typing_speed': typing_speed,
        'backspace_rate': backspace_rate
    }
    
    metrics = {
        'wpm': typing_speed,
        'iki_mean': iki_stats['mean'],
        'iki_std': iki_stats['std'],
        'bsr': backspace_rate
    }
    
    return round(focus_index, 1), details, metrics

#介面
class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("專注力分析系統 - 登入")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        
        # 標題
        title = tk.Label(root, text="專注力分析系統", font=("Arial", 20, "bold"))
        title.pack(pady=20)
        
        # 帳號
        frame_account = tk.Frame(root)
        frame_account.pack(pady=10)
        tk.Label(frame_account, text="帳號:", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.entry_account = tk.Entry(frame_account, font=("Arial", 12), width=20)
        self.entry_account.pack(side=tk.LEFT, padx=5)
        
        # 密碼
        frame_password = tk.Frame(root)
        frame_password.pack(pady=10)
        tk.Label(frame_password, text="密碼:", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.entry_password = tk.Entry(frame_password, font=("Arial", 12), width=20, show="*")
        self.entry_password.pack(side=tk.LEFT, padx=5)
        
        # 按鈕
        frame_buttons = tk.Frame(root)
        frame_buttons.pack(pady=20)
        
        btn_login = tk.Button(frame_buttons, text="登入", font=("Arial", 12), 
                              width=10, command=self.do_login, bg="#4CAF50", fg="white")
        btn_login.pack(side=tk.LEFT, padx=10)
        
        btn_signup = tk.Button(frame_buttons, text="註冊", font=("Arial", 12), 
                               width=10, command=self.do_signup, bg="#2196F3", fg="white")
        btn_signup.pack(side=tk.LEFT, padx=10)
        
        # Enter 鍵綁定
        self.entry_password.bind('<Return>', lambda e: self.do_login())
    
    def do_login(self):
        account = self.entry_account.get().strip()
        password = self.entry_password.get().strip()
        
        if not account or not password:
            messagebox.showwarning("提示", "請輸入帳號和密碼")
            return
        
        user_id, msg = login(account, password)
        if user_id:
            global current_user_id
            current_user_id = user_id
            messagebox.showinfo("成功", f"歡迎 {account}！")
            self.root.destroy()
            self.open_main_window(account)
        else:
            messagebox.showerror("錯誤", msg)
    
    def do_signup(self):
        account = self.entry_account.get().strip()
        password = self.entry_password.get().strip()
        
        if not account or not password:
            messagebox.showwarning("提示", "請輸入帳號和密碼")
            return
        
        if len(password) < 4:
            messagebox.showwarning("提示", "密碼至少 4 個字元")
            return
        
        success, msg = sign_up(account, password)
        if success:
            messagebox.showinfo("成功", msg)
            # 自動登入
            user_id, _ = login(account, password)
            if user_id:
                global current_user_id
                current_user_id = user_id
                self.root.destroy()
                self.open_main_window(account)
        else:
            messagebox.showerror("錯誤", msg)
    
    def open_main_window(self, account):
        main_root = tk.Tk()
        MainWindow(main_root, account)
        main_root.mainloop()

class MainWindow:
    def __init__(self, root, account):
        self.root = root
        self.account = account
        self.root.title(f"專注力監測 - {account}")
        self.root.geometry("500x600")
        self.root.resizable(False, False)
        
        # 標題區
        header = tk.Frame(root, bg="#2196F3", height=60)
        header.pack(fill=tk.X)
        tk.Label(header, text=f"使用者: {account}", font=("Arial", 14), 
                bg="#2196F3", fg="white").pack(side=tk.LEFT, padx=20, pady=15)
        
        # 專注度顯示區
        self.focus_frame = tk.Frame(root, bg="#f0f0f0", height=200)
        self.focus_frame.pack(fill=tk.X, pady=20, padx=20)
        
        tk.Label(self.focus_frame, text="當前專注指數", font=("Arial", 16), 
                bg="#f0f0f0").pack(pady=10)
        
        self.label_score = tk.Label(self.focus_frame, text="--", 
                                    font=("Arial", 48, "bold"), bg="#f0f0f0")
        self.label_score.pack()
        
        self.label_status = tk.Label(self.focus_frame, text="尚未開始監測", 
                                     font=("Arial", 14), bg="#f0f0f0")
        self.label_status.pack(pady=5)
        
        # 統計資訊區
        stats_frame = tk.Frame(root, bg="white")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(stats_frame, text="即時統計", font=("Arial", 14, "bold"), 
                bg="white").pack(anchor=tk.W, padx=10, pady=5)
        
        self.label_keys = tk.Label(stats_frame, text="總按鍵數: 0", 
                                   font=("Arial", 11), bg="white")
        self.label_keys.pack(anchor=tk.W, padx=20, pady=2)
        
        self.label_wpm = tk.Label(stats_frame, text="打字速度: 0 keys/min", 
                                 font=("Arial", 11), bg="white")
        self.label_wpm.pack(anchor=tk.W, padx=20, pady=2)
        
        self.label_backspace = tk.Label(stats_frame, text="修正次數: 0", 
                                       font=("Arial", 11), bg="white")
        self.label_backspace.pack(anchor=tk.W, padx=20, pady=2)
        
        self.label_time = tk.Label(stats_frame, text="監測時間: 0 秒", 
                                  font=("Arial", 11), bg="white")
        self.label_time.pack(anchor=tk.W, padx=20, pady=2)
        
        # 控制按鈕
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=20)
        
        self.btn_start = tk.Button(btn_frame, text="開始監測", font=("Arial", 12), 
                                   width=12, command=self.start_monitoring, 
                                   bg="#4CAF50", fg="white", height=2)
        self.btn_start.pack(side=tk.LEFT, padx=10)
        
        self.btn_stop = tk.Button(btn_frame, text="停止監測", font=("Arial", 12), 
                                 width=12, command=self.stop_monitoring, 
                                 bg="#f44336", fg="white", height=2, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        
        # 更新執行緒
        self.is_running = False
        self.update_thread = None
    
    def start_monitoring(self):
        global is_monitoring, A, b
        A = [[], []]
        b = 0
        is_monitoring = True
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.label_status.config(text="監測中...")
        
        # 開始鍵盤監聽
        keyboard.on_press(on_key)
        
        # 開始更新執行緒
        self.is_running = True
        self.update_thread = threading.Thread(target=self.update_display, daemon=True)
        self.update_thread.start()
    
    def stop_monitoring(self):
        global is_monitoring
        is_monitoring = False
        self.is_running = False
        
        keyboard.unhook_all()
        
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        
        # 計算最終結果
        if len(A[1]) > 1:
            focus_score, details, metrics = calculate_focus_index(A[0], A[1], b)
            
            # 儲存到資料庫
            total_time = A[1][-1] - A[1][0]
            save_focus_record(current_user_id, focus_score, 
                            metrics['wpm'], metrics['iki_mean'], metrics['iki_std'],
                            metrics['bsr'], len(A[0]), total_time)
            
            messagebox.showinfo("分析完成", 
                              f"專注指數: {focus_score}/100\n"
                              f"打字速度: {details['typing_speed']:.2f} keys/min\n"
                              f"錯誤率: {details['backspace_rate']:.2f}%\n\n"
                              f"記錄已儲存到資料庫")
        
        self.label_status.config(text="已停止監測")
    
    def update_display(self):
        """每秒更新顯示"""
        while self.is_running:
            if len(A[1]) > 1:
                focus_score, details, metrics = calculate_focus_index(A[0], A[1], b)
                total_time = A[1][-1] - A[1][0]
                
                # 更新顯示
                self.label_score.config(text=f"{focus_score}")
                
                # 根據分數改變顏色
                if focus_score >= 70:
                    self.focus_frame.config(bg="#4CAF50")
                    self.label_score.config(bg="#4CAF50", fg="white")
                    self.label_status.config(text="高度專注", bg="#4CAF50", fg="white")
                elif focus_score >= 40:
                    self.focus_frame.config(bg="#FFC107")
                    self.label_score.config(bg="#FFC107", fg="white")
                    self.label_status.config(text="中度專注", bg="#FFC107", fg="white")
                else:
                    self.focus_frame.config(bg="#f44336")
                    self.label_score.config(bg="#f44336", fg="white")
                    self.label_status.config(text="注意力不足", bg="#f44336", fg="white")
                
                # 更新統計
                self.label_keys.config(text=f"總按鍵數: {len(A[0])}")
                self.label_wpm.config(text=f"打字速度: {details['typing_speed']:.2f} keys/min")
                self.label_backspace.config(text=f"修正次數: {b}")
                self.label_time.config(text=f"監測時間: {total_time:.1f} 秒")
            
            time.sleep(1)  # 每秒更新一次

# ===== 主程式 =====
def main():
    
    # 開啟登入視窗
    root = tk.Tk()
    LoginWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()