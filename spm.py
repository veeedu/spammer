import tkinter as tk
import pyautogui
import threading
import time

spamming = False
spam_thread = None

def start_spam(message, delay):
    global spamming
    spamming = True
    while spamming:
        pyautogui.typewrite(message, interval=0.03)
        pyautogui.press('enter')
        time.sleep(delay)

def on_start():
    global spam_thread
    msg = message_entry.get()
    try:
        delay = float(delay_entry.get())
    except:
        delay = 1.0
    if msg and not spamming:
        spam_thread = threading.Thread(target=start_spam, args=(msg, delay))
        spam_thread.daemon = True
        spam_thread.start()

def on_stop():
    global spamming
    spamming = False

root = tk.Tk()
root.title("Keyboard Spammer")

tk.Label(root, text="Message:").pack()
message_entry = tk.Entry(root, width=40)
message_entry.pack()

tk.Label(root, text="Delay (sec):").pack()
delay_entry = tk.Entry(root, width=10)
delay_entry.insert(0, "0.5")
delay_entry.pack()

tk.Button(root, text="▶ Start (Alt+P)", command=on_start).pack(pady=5)
tk.Button(root, text="⏹ Stop (Alt+L)", command=on_stop).pack(pady=5)

root.mainloop()
