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
current_baseline = None  # 儲存當前使用者的基準線

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
    
def get_baseline(user_id):
    #取得使用者基準線
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    cursor.execute(
        "SELECT wpm, iki_mean, iki_std, bsr FROM baseline WHERE user_id = %s",
        (user_id,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if result:
        return {
            'wpm': result[0],
            'iki_mean': result[1],
            'iki_std': result[2],
            'bsr': result[3]
        }
    return None

def save_baseline(user_id, wpm, iki_mean, iki_std, bsr):
    """儲存或更新使用者基準線"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        # 使用 ON DUPLICATE KEY UPDATE 來處理新增/更新
        cursor.execute('''
            INSERT INTO baseline (user_id, wpm, iki_mean, iki_std, bsr, sample_count)
            VALUES (%s, %s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE 
                wpm = VALUES(wpm),
                iki_mean = VALUES(iki_mean),
                iki_std = VALUES(iki_std),
                bsr = VALUES(bsr),
                sample_count = sample_count + 1,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, wpm, iki_mean, iki_std, bsr))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"儲存基準線失敗: {err}")
        return False
    finally:
        cursor.close()
        conn.close()
        
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

def calculate_focus_index(keys, timestamps, backspace_count, baseline=None):
    #計算專注指數 (0-100分)
    if len(timestamps) < 2:
        return 0, {}, {}
    
    total_time = timestamps[-1] - timestamps[0]
    typing_speed = (len(keys) / total_time) * 60 if total_time > 0 else 0
    iki_stats = calculate_iki_stats(timestamps)
    backspace_rate = (backspace_count / len(keys)) * 100 if keys else 0
    
    # 評分
    if baseline is None:
        # 無基準線：絕對評分
        speed_score = min(30, (typing_speed / 60) * 30)
        consistency_score = max(0, 30 - (iki_stats['std'] / 100) * 30)
        error_score = max(0, 40 - backspace_rate * 2)
    else:
        # 有基準線：偏離度評分
        # WPM 偏離度（30分）
        if baseline['wpm'] > 0:
            wpm_deviation = abs(typing_speed - baseline['wpm']) / baseline['wpm']
            speed_score = max(0, 30 * (1 - min(1, wpm_deviation)))
        else:
            speed_score = 15
        
        # IKI 偏離度（30分）
        if baseline['iki_mean'] > 0:
            iki_deviation = abs(iki_stats['mean'] - baseline['iki_mean']) / baseline['iki_mean']
            consistency_score = max(0, 30 * (1 - min(1, iki_deviation)))
        else:
            consistency_score = 15
        
        # BSR 偏離度（40分）
        bsr_base = baseline['bsr'] if baseline['bsr'] > 0 else 1
        bsr_deviation = abs(backspace_rate - baseline['bsr']) / (bsr_base + 5)
        error_score = max(0, 40 * (1 - min(1, bsr_deviation)))
    
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
            global current_user_id, current_baseline
            current_user_id = user_id
            current_baseline = get_baseline(user_id)
            
            self.root.destroy()
            
            # 檢查是否有基準線
            if current_baseline is None:
                # 新用戶，需要建立基準線
                self.open_baseline_setup(account)
            else:
                # 已有基準線，直接進入主視窗
                messagebox.showinfo("成功", f"歡迎回來 {account}！")
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
            user_id, _ = login(account, password)
            if user_id:
                global current_user_id
                current_user_id = user_id
                self.root.destroy()
                # 新用戶需要建立基準線
                self.open_baseline_setup(account)
        else:
            messagebox.showerror("錯誤", msg)
    
    def open_baseline_setup(self, account):
        #開啟基準線設定視窗
        baseline_root = tk.Tk()
        BaselineSetupWindow(baseline_root, account)
        baseline_root.mainloop()
        
    def open_main_window(self, account):
        """開啟主視窗"""
        main_root = tk.Tk()
        MainWindow(main_root, account)
        main_root.mainloop()
        
class BaselineSetupWindow:
    def __init__(self, root, account):
        self.root = root
        self.account = account
        self.root.title(f"建立基準線 - {account}")
        self.root.geometry("600x500")
        
        # 說明區
        header = tk.Frame(root, bg="#2196F3")
        header.pack(fill=tk.X)
        
        tk.Label(header, text="建立個人化基準線", font=("Arial", 18, "bold"),
                bg="#2196F3", fg="white").pack(pady=15)
        
        # 主內容區 - 使用 grid 布局更好控制
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH,  padx=20, pady=20)
        
        # 說明文字
        info_frame = tk.Frame(main_frame, bg="#f0f0f0", relief=tk.RIDGE, bd=2)
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(info_frame, text="歡迎使用專注力分析系統！", 
                font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=(10, 5))
        
        tk.Label(info_frame, 
                text="首次使用需要建立您的「個人化基準線」。\n這將作為日後評估專注度的參考標準。", 
                font=("Arial", 10), bg="#f0f0f0", justify=tk.CENTER).pack(pady=5)
        
        # 步驟說明
        steps_frame = tk.Frame(info_frame, bg="#f0f0f0")
        steps_frame.pack(pady=10)
        
        steps = [
            "點擊下方「開始測試」按鈕",
            "在習慣的環境下正常打字 30 秒",
            "系統會自動計算並儲存基準值"
        ]
        
        for step in steps:
            tk.Label(steps_frame, text=step, font=("Arial", 10), 
                    bg="#f0f0f0", anchor=tk.W).pack(anchor=tk.W, padx=20, pady=2)
        
        tk.Label(info_frame, text="建議：選擇一個安靜、專注的時段進行測試", 
                font=("Arial", 9, "italic"), bg="#f0f0f0", fg="#666").pack(pady=(5, 10))
        
        # 狀態顯示區
        status_frame = tk.Frame(main_frame)
        status_frame.pack(fill=tk.BOTH, expand=True)
        
        self.label_status = tk.Label(status_frame, text="準備就緒", 
                                     font=("Arial", 14, "bold"))
        self.label_status.pack()
        
        self.label_timer = tk.Label(status_frame, text="", 
                                    font=("Arial", 14, "bold"))
        self.label_timer.pack()
        
        # 按鈕區
        button_frame = tk.Frame(root)
        button_frame.pack(side=tk.BOTTOM)
        
        self.btn_start = tk.Button(button_frame, text="開始測試 (30秒)", 
                                   font=("Arial", 14, "bold"),
                                   width=22, height=2, 
                                   command=self.start_test,
                                   bg="#4CAF50",
                                   cursor="hand2",
                                   relief=tk.RAISED,
                                   bd=3)
        self.btn_start.pack(pady=20)
        
        self.is_testing = False
        self.test_duration = 30  # 測試時長（秒）
    
    def start_test(self):
        global is_monitoring, A, b
        A = [[], []]
        b = 0
        is_monitoring = True
        self.is_testing = True
        
        self.btn_start.config(state=tk.DISABLED)
        self.label_status.config(text="測試進行中...", fg="green")
        
        keyboard.on_press(on_key)
        
        # 開始倒數計時
        self.countdown(self.test_duration)
    
    def countdown(self, remaining):
        if remaining > 0 and self.is_testing:
            self.label_timer.config(text=f"{remaining} 秒", fg="blue")
            self.root.after(1000, self.countdown, remaining - 1)
        else:
            self.finish_test()
    
    def finish_test(self):
        global is_monitoring, current_baseline
        is_monitoring = False
        self.is_testing = False
        keyboard.unhook_all()
        
        self.label_timer.config(text="")
        
        # 檢查數據是否足夠
        if len(A[1]) < 10:
            messagebox.showwarning("數據不足", 
                                 "測試期間按鍵太少，請重新測試。\n建議持續打字至少30秒。")
            self.btn_start.config(state=tk.NORMAL)
            self.label_status.config(text="準備就緒，點擊開始")
            return
        
        # 計算基準線
        total_time = A[1][-1] - A[1][0]
        wpm = (len(A[0]) / total_time) * 60 if total_time > 0 else 0
        iki_stats = calculate_iki_stats(A[1])
        bsr = (b / len(A[0])) * 100 if A[0] else 0
        
        # 儲存到資料庫
        if save_baseline(current_user_id, wpm, iki_stats['mean'], iki_stats['std'], bsr):
            current_baseline = {
                'wpm': wpm,
                'iki_mean': iki_stats['mean'],
                'iki_std': iki_stats['std'],
                'bsr': bsr
            }
            
            messagebox.showinfo("基準線建立完成！", 
                              f"您的個人化基準值：\n\n"
                              f"打字速度: {wpm:.2f} keys/min\n"
                              f"平均鍵間時長: {iki_stats['mean']:.2f} ms\n"
                              f"錯誤率: {bsr:.2f}%\n\n"
                              f"基準線已儲存，現在開始使用系統！")
            
            self.root.destroy()
            self.open_main_window()
        else:
            messagebox.showerror("錯誤", "儲存基準線失敗，請重試")
            self.btn_start.config(state=tk.NORMAL)
            
    def open_main_window(self):
        main_root = tk.Tk()
        MainWindow(main_root, self.account)
        main_root.mainloop()

class MainWindow:
    def __init__(self, root, account):
        self.root = root
        self.account = account
        self.root.title(f"專注力監測 - {account}")
        self.root.geometry("550x600")
        
        # 標題區
        header = tk.Frame(root, bg="#2196F3", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        header_left = tk.Frame(header, bg="#2196F3")
        header_left.pack(side=tk.LEFT, padx=20)
        
        tk.Label(header_left, text=f"使用者: {account}", font=("Arial", 14, "bold"), 
                bg="#2196F3", fg="white").pack(anchor=tk.W)
        
        baseline_status = "已建立基準線" if current_baseline else "未建立基準線"
        tk.Label(header_left, text=baseline_status, font=("Arial", 9), 
                bg="#2196F3", fg="white").pack(anchor=tk.W)
        
        # 登出按鈕
        btn_logout = tk.Button(header, text="登出", font=("Arial", 10),
                              width=8, command=self.logout,
                              bg="white", fg="#2196F3", cursor="hand2")
        btn_logout.pack(side=tk.RIGHT, padx=20, pady=20)
        
        # 專注度顯示區
        self.focus_frame = tk.Frame(root, bg="#f0f0f0", height=180)
        self.focus_frame.pack(fill=tk.X, pady=15, padx=15)
        self.focus_frame.pack_propagate(False)
        
        tk.Label(self.focus_frame, text="當前專注指數", font=("Arial", 14), 
                bg="#f0f0f0", fg="#666").pack(pady=(15, 5))
        
        self.label_score = tk.Label(self.focus_frame, text="--", 
                                    font=("Arial", 52, "bold"), bg="#f0f0f0")
        self.label_score.pack()
        
        self.label_status = tk.Label(self.focus_frame, text="尚未開始監測", 
                                     font=("Arial", 12), bg="#f0f0f0")
        self.label_status.pack(pady=5)
        
        # 統計資訊區
        stats_frame = tk.Frame(root, bg="white", relief=tk.RIDGE, bd=1)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        tk.Label(stats_frame, text="即時統計", font=("Arial", 13, "bold"), 
                bg="white").pack(anchor=tk.W, padx=15, pady=10)
        
        stats_grid = tk.Frame(stats_frame, bg="white")
        stats_grid.pack(fill=tk.X, padx=15)
        
        # 使用 grid 排列統計資訊
        self.label_keys = tk.Label(stats_grid, text="總按鍵數: 0", 
                                   font=("Arial", 11), bg="white", anchor=tk.W)
        self.label_keys.grid(row=0, column=0, sticky=tk.W, pady=5, padx=10)
        
        self.label_wpm = tk.Label(stats_grid, text="打字速度: 0 keys/min", 
                                 font=("Arial", 11), bg="white", anchor=tk.W)
        self.label_wpm.grid(row=0, column=1, sticky=tk.W, pady=5, padx=10)
        
        self.label_backspace = tk.Label(stats_grid, text="修正次數: 0", 
                                       font=("Arial", 11), bg="white", anchor=tk.W)
        self.label_backspace.grid(row=1, column=0, sticky=tk.W, pady=5, padx=10)
        
        self.label_time = tk.Label(stats_grid, text="監測時間: 0 秒", 
                                  font=("Arial", 11), bg="white", anchor=tk.W)
        self.label_time.grid(row=1, column=1, sticky=tk.W, pady=5, padx=10)
        
        # 空白區域
        tk.Label(stats_frame, text="", bg="white").pack(pady=10)
        
        # 控制按鈕
        btn_frame = tk.Frame(root, bg="white")
        btn_frame.pack(side=tk.BOTTOM, pady=20)
        
        self.btn_start = tk.Button(btn_frame, text="開始監測", font=("Arial", 11, "bold"), 
                                   width=12, height=2, command=self.start_monitoring, 
                                   bg="#4CAF50", fg="white", cursor="hand2")
        self.btn_start.grid(row=0, column=0, padx=5)
        
        self.btn_stop = tk.Button(btn_frame, text="停止監測", font=("Arial", 11, "bold"), 
                                 width=12, height=2, command=self.stop_monitoring, 
                                 bg="#f44336", fg="white", state=tk.DISABLED, cursor="hand2")
        self.btn_stop.grid(row=0, column=1, padx=5)
        
        self.btn_reset_baseline = tk.Button(btn_frame, text="重設基準線", font=("Arial", 11, "bold"),
                                           width=12, height=2, command=self.reset_baseline,
                                           bg="#FF9800", fg="white", cursor="hand2")
        self.btn_reset_baseline.grid(row=0, column=2, padx=5)
        
        self.is_running = False
        self.update_thread = None
        
    def logout(self):
        #登出功能
        global is_monitoring
        
        # 如果正在監測，先停止
        if is_monitoring:
            result = messagebox.askyesno("確認登出", 
                                        "目前正在監測中，登出將停止監測。\n確定要登出嗎？")
            if not result:
                return
            self.stop_monitoring()
        else:
            result = messagebox.askyesno("確認登出", "確定要登出嗎？")
            if not result:
                return
        
        # 關閉當前視窗
        self.root.destroy()
        
        # 重新開啟登入視窗
        login_root = tk.Tk()
        LoginWindow(login_root)
        login_root.mainloop()
    
    def start_monitoring(self):
        global is_monitoring, A, b
        A = [[], []]
        b = 0
        is_monitoring = True
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_reset_baseline.config(state=tk.DISABLED)
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
        self.btn_reset_baseline.config(state=tk.NORMAL)
        
        # 計算最終結果
        if len(A[1]) > 1:
            focus_score, details, metrics = calculate_focus_index(A[0], A[1], b, current_baseline)
            
            # 儲存到資料庫
            total_time = A[1][-1] - A[1][0]
            save_focus_record(current_user_id, focus_score, 
                            metrics['wpm'], metrics['iki_mean'], metrics['iki_std'],
                            metrics['bsr'], len(A[0]), total_time)
            
            baseline_info = "\n使用個人化基準線評分" if current_baseline else "\n使用絕對評分（建議設定基準線）"
            
            messagebox.showinfo("分析完成", 
                              f"專注指數: {focus_score}/100\n"
                              f"打字速度: {details['typing_speed']:.2f} keys/min\n"
                              f"錯誤率: {details['backspace_rate']:.2f}%\n\n"
                              f"{baseline_info}\n\n"
                              f"記錄已儲存到資料庫")
        
        self.label_status.config(text="已停止監測")
        
    def reset_baseline(self):
        #重新設定基準線
        result = messagebox.askyesno("確認", 
                                    "確定要重新測試基準線嗎？\n這將覆蓋目前的基準值。")
        if result:
            self.root.destroy()
            baseline_root = tk.Tk()
            BaselineSetupWindow(baseline_root, self.account)
            baseline_root.mainloop()
            
    def update_display(self):
        """每秒更新顯示"""
        while self.is_running:
            if len(A[1]) > 1:
                focus_score, details, metrics = calculate_focus_index(A[0], A[1], b, current_baseline)
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