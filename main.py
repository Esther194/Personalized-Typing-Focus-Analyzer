import keyboard
import time
import sys
import numpy as np
import csv

A = [[], []]#輸入值跟時間
b = 0#backspace計數

def on_key(event):
    sys.stdout.flush()  # 強制刷新輸出緩衝區
    if event.name == 'esc':  # 按下 esc 結束
        keyboard.unhook_all()
    A[0].append(event.name)#輸入值
    A[1].append(time.time()) #時間

def keys_to_string(keys):
    global b
    result = ""
    for key in keys:
        if key == 'backspace':
            b+=1
            if result:  # 如果有字符可以刪除
                result = result[:-1]  # 刪除最後一個字符
        elif key == 'enter':
            result += '\n'  # 換行
        elif key == 'space':
            result += ' '   # 空格
        elif key == 'tab':
            result += '\t'  # Tab
        elif len(key) == 1:  # 單個字符（字母、數字、符號）
            result += key
        # 其他特殊鍵（如 ctrl, alt, shift）不處理
    return result



def calculate_iki_stats(timestamps):
    """計算鍵間時間統計"""
    if len(timestamps) < 2:
        return {'mean': 0, 'std': 0}
    
    iki_times = []
    for i in range(1, len(timestamps)):
        iki = (timestamps[i] - timestamps[i-1]) * 1000  # 轉毫秒
        if iki < 2000:  # 過濾超過2秒的異常值
            iki_times.append(iki)
    
    if not iki_times:
        return {'mean': 0, 'std': 0}
    
    return {
        'mean': np.mean(iki_times),
        'std': np.std(iki_times)
    }

keyboard.on_press(on_key)
keyboard.wait('esc')# 按下 esc 結束

if len(A[1]) > 1:
    total_time = A[1][-1] - A[1][0]
    typing_speed = (len(A[0]) / total_time) * 60 if total_time > 0 else 0  # kpm
    text_content = keys_to_string(A[0])
    iki_stats = calculate_iki_stats(A[1])  # 回傳 {'mean': ..., 'std': ...}
    iki_mean = float(iki_stats['mean'])
    iki_std = float(iki_stats['std'])
    
    # 寫入摘要 CSV
    with open("typing0.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["total_time", "typing_speed", "text_content", "iki_mean", "iki_std"])
        writer.writerow([total_time, typing_speed, iki_mean, iki_std, text_content])
    
    