import cv2
import numpy as np
import pyautogui
import time
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
import threading
import sounddevice as sd
import soundfile as sf
import os
import subprocess
import tempfile

class ScreenRecorder:
    def __init__(self):
        self.recording = False
        self.region = None
        self.fps = 30
        self.output_file = ""
        self.audio_file = ""
        self.final_output = ""
        self.fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = None
        self.audio_stream = None
        self.audio_frames = []
        self.sample_rate = 44100

    def select_region(self):
        """使用GUI选择录制区域，添加全屏选项"""
        root = tk.Tk()
        root.withdraw()
        # 询问是否全屏录制
        if messagebox.askyesno("选择录制区域", "是否录制全屏？"):
            self.region = None  # 全屏录制
            print("选择全屏录制")
            return
        # 创建透明窗口选择区域
        selection_window = tk.Toplevel(root)
        selection_window.attributes('-fullscreen', True)
        selection_window.attributes('-alpha', 0.3)
        selection_window.configure(background='black')
        canvas = tk.Canvas(selection_window, bg='black', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        start_x, start_y = 0, 0
        rect = None

        def on_mouse_down(event):
            nonlocal start_x, start_y, rect
            start_x, start_y = event.x, event.y
            rect = canvas.create_rectangle(start_x, start_y, start_x, start_y,
                                         outline='red', width=2, fill='white')

        def on_mouse_move(event):
            nonlocal rect
            if rect:
                canvas.coords(rect, start_x, start_y, event.x, event.y)

        def on_mouse_up(event):
            nonlocal self
            end_x, end_y = event.x, event.y
            x1, y1 = min(start_x, end_x), min(start_y, end_y)
            x2, y2 = max(start_x, end_x), max(start_y, end_y)
            self.region = (x1, y1, x2 - x1, y2 - y1)
            selection_window.destroy()
            print(f"已选择区域: {self.region}")

        canvas.bind('<Button-1>', on_mouse_down)
        canvas.bind('<B1-Motion>', on_mouse_move)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)
        selection_window.wait_window()

    def start_audio_recording(self):
        """开始录制音频"""
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"音频录制错误: {status}")
            self.audio_frames.append(indata.copy())
        self.audio_frames = []
        try:
            self.audio_stream = sd.InputStream(
                samplerate=self.sample_rate, channels=2, callback=audio_callback, dtype='float32')
            self.audio_stream.start()
            print("音频录制开始")
        except Exception as e:
            print(f"音频录制初始化失败: {e}")
            raise

    def stop_audio_recording(self):
        """停止音频录制并保存"""
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            if self.audio_frames:
                audio_data = np.concatenate(self.audio_frames)
                self.audio_file = tempfile.mktemp(suffix='.wav')
                sf.write(self.audio_file, audio_data, self.sample_rate)
                print(f"音频保存至: {self.audio_file}")
            else:
                print("无音频数据")

    def start_recording(self):
        """开始录制"""
        if self.recording:
            print("已经在录制中")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = f"screen_record_{timestamp}.mp4"
        self.audio_file = f"audio_record_{timestamp}.wav"
        self.final_output = f"final_record_{timestamp}.mp4"
        width, height = pyautogui.size() if not self.region else (self.region[2], self.region[3])
        try:
            self.video_writer = cv2.VideoWriter(self.output_file, self.fourcc, self.fps, (width, height))
            self.start_audio_recording()
            self.recording = True
            print(f"开始录制到 {self.final_output}... (按Ctrl+C停止)")
            while self.recording:
                frame_start_time = time.time()
                img = pyautogui.screenshot(region=self.region)
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                self.video_writer.write(frame)
                elapsed = time.time() - frame_start_time
                time.sleep(max(0, (1 / self.fps) - elapsed))
        except KeyboardInterrupt:
            self.stop_recording()
        except Exception as e:
            print(f"录制出错: {e}")
            self.stop_recording()

    def stop_recording(self):
        """停止录制并合并音视频"""
        if not self.recording:
            print("当前没有在录制")
            return
        self.recording = False
        if self.video_writer:
            self.video_writer.release()
        self.stop_audio_recording()
        if os.path.exists(self.audio_file):
            print("正在合并音视频...")
            try:
                cmd = ['ffmpeg', '-y', '-i', self.output_file, '-i', self.audio_file,
                       '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                       '-shortest', self.final_output]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    os.remove(self.output_file)
                    os.remove(self.audio_file)
                    print(f"录制完成，文件保存为: {self.final_output}")
                else:
                    print(f"合并音视频失败: {result.stderr}")
                    print(f"视频文件(无声): {self.output_file}, 音频文件: {self.audio_file}")
            except Exception as e:
                print(f"合并音视频失败: {e}")
                print(f"视频文件(无声): {self.output_file}, 音频文件: {self.audio_file}")
        else:
            print(f"录制完成(无音频)，文件保存为: {self.output_file}")

def check_ffmpeg():
    """检查ffmpeg是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print("ffmpeg已安装:", result.stdout.split('\n')[0])
        return True
    except Exception as e:
        print(f"ffmpeg未安装或不可用: {e}")
        return False

def main():
    if not check_ffmpeg():
        messagebox.showerror("错误", "请安装ffmpeg并添加到系统PATH")
        return
    recorder = ScreenRecorder()
    print("=== 屏幕录制工具 ===")
    print("1. 全屏录制")
    print("2. 选择区域录制")
    choice = input("请选择录制模式 (1/2): ")
    if choice == "2":
        recorder.select_region()
    recording_thread = threading.Thread(target=recorder.start_recording)
    recording_thread.start()
    root = tk.Tk()
    root.title("屏幕录制控制")
    root.geometry("300x150")
    tk.Label(root, text="录制中...").pack(pady=10)
    tk.Button(root, text="停止录制", command=lambda: [recorder.stop_recording(), root.destroy()], bg='red', fg='white').pack(pady=20)
    root.mainloop()

if __name__ == "__main__":
    main()