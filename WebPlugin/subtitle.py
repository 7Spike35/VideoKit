import whisper
import os
import datetime, time
import subprocess  # 用于获取视频时长
from zhconv import convert  # 简繁体转换
from tqdm import tqdm


def find_files(path, suffix):
    """ 获取指定目录下所有指定后缀的文件 """
    return [os.path.join(root, file) for root, _, files in os.walk(path) for file in files if
            file.endswith('.' + suffix)]


def get_video_duration(file_path):
    """ 使用 ffprobe 获取视频时长（单位：秒） """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
             file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        return 0.0


def seconds_to_hmsm(seconds):
    """ 将秒转换为 H:M:S,ms 格式 """
    hours = str(int(seconds // 3600)).zfill(2)
    minutes = str(int((seconds % 3600) // 60)).zfill(2)
    sec = str(int(seconds % 60)).zfill(2)
    milliseconds = str(int((seconds - int(seconds)) * 1000)).zfill(3)
    return f"{hours}:{minutes}:{sec},{milliseconds}"


def main():
    file_path = r'E:\dl\video'
    mp4_files = find_files(file_path, suffix='mp4')

    # 加载 Whisper 模型
    model = whisper.load_model('small')

    for file in tqdm(mp4_files):
        save_file = file[:-3] + "srt"
        if os.path.exists(save_file):
            time.sleep(0.01)
            continue

        start_time = datetime.datetime.now()
        print(f'正在识别：{file} -- {start_time.strftime("%Y-%m-%d %H:%M:%S")}')

        duration = get_video_duration(file)
        duration_hmsm = seconds_to_hmsm(duration)
        print(f'视频时长：{duration_hmsm}')

        # 语音识别
        res = model.transcribe(file, fp16=False, language='Chinese')

        # 保存字幕文件
        with open(save_file, 'w', encoding='utf-8') as f:
            for i, r in enumerate(res['segments'], start=1):
                f.write(f"{i}\n")
                f.write(f"{seconds_to_hmsm(r['start'])} --> {seconds_to_hmsm(r['end'])}\n")
                f.write(f"{convert(r['text'], 'zh-cn')}\n\n")

        end_time = datetime.datetime.now()
        print(f'完成识别：{file} -- {end_time.strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'花费时间: {end_time - start_time}')


if __name__ == "__main__":
    main()