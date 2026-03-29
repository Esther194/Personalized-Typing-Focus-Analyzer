import keyboard
import time
import sys

A = [[], []]

def on_key(event):
    
    sys.stdout.flush()  # 強制刷新輸出緩衝區
    if event.name == 'esc':  # 按下 esc 結束
        keyboard.unhook_all()
    A[0].append(event.name)
    A[1].append(time.time()) 
    #print(A[1][len(A[1])-1])
    

keyboard.on_press(on_key)
keyboard.wait('esc')# 按下 esc 結束
x=A[1][len(A[1])-1]-A[1][0]#輸出秒數相減
print(x)
#