import whisper
import os
import datetime
import subprocess
from zhconv import convert
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch


def find_files(path, suffix):
    """获取指定目录下所有指定后缀的文件"""
    return [os.path.join(root, file) for root, _, files in os.walk(path)
            for file in files if file.endswith(f'.{suffix}')]


def get_video_duration(file_path):
    """使用ffprobe获取视频时长（秒）"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        return 0.0


def seconds_to_hmsm(seconds):
    """将秒转换为H:M:S,ms格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{sec:02d},{milliseconds:03d}"


class Translator:
    """翻译器封装类"""

    def __init__(self):
        self.models = {}
        self.tokenizers = {}

    def load_model(self, src_lang, tgt_lang):
        """动态加载翻译模型"""
        if (src_lang, tgt_lang) in self.models:
            return
        if(src_lang=='zh'):
            model_name = f'D:\pytorchusetrue\opus-mt-zh-en'
        else:
            model_name = f'D:\pytorchusetrue\opus-mt-en-zh'
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            self.models[(src_lang, tgt_lang)] = model
            self.tokenizers[(src_lang, tgt_lang)] = tokenizer
        except Exception as e:
            raise ValueError(f"不支持的语言对: {src_lang}->{tgt_lang}") from e

    def translate(self, text, src_lang, tgt_lang):
        """执行翻译"""
        self.load_model(src_lang, tgt_lang)
        tokenizer = self.tokenizers[(src_lang, tgt_lang)]
        model = self.models[(src_lang, tgt_lang)]

        inputs = tokenizer([text], return_tensors="pt", padding=True)
        translated = model.generate(**inputs)
        return tokenizer.decode(translated[0], skip_special_tokens=True)


def main():
    # 配置参数
    video_path = r'E:\dl\videoss'  # 修改为你的视频目录
    model_size = 'small'  # Whisper模型大小

    # 初始化组件
    whisper_model = whisper.load_model(model_size)
    translator = Translator()

    # 获取视频文件
    mp4_files = find_files(video_path, 'mp4')

    for file in tqdm(mp4_files):
        base_name = os.path.splitext(file)[0]
        srt_path = f"{base_name}.srt"
        en_srt_path = f"{base_name}_EN.srt"
        zh_srt_path = f"{base_name}_ZH.srt"

        # 跳过已处理文件
        if os.path.exists(srt_path) and os.path.exists(en_srt_path) and os.path.exists(zh_srt_path):
            continue

        # 语音识别
        start_time = datetime.datetime.now()
        print(f"\n开始处理: {file} ({start_time.strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"视频时长: {seconds_to_hmsm(get_video_duration(file))}")

        result = whisper_model.transcribe(file, fp16=torch.cuda.is_available())
        src_lang = result.get('language', 'en')
        print(f"检测到语言: {src_lang.upper()}")

        # 生成原始字幕 - 确保使用UTF-8编码
        try:
            with open(srt_path, 'w', encoding='utf-8-sig') as f:  # 使用utf-8-sig处理BOM
                for i, seg in enumerate(result['segments'], 1):
                    text = convert(seg['text'], 'zh-cn') if src_lang == 'zh' else seg['text']
                    f.write(f"{i}\n")
                    f.write(f"{seconds_to_hmsm(seg['start'])} --> {seconds_to_hmsm(seg['end'])}\n")
                    f.write(f"{text}\n\n")
        except UnicodeEncodeError as e:
            print(f"写入原始字幕文件时编码错误: {e}")
            continue

        # 生成翻译字幕 - 确保正确处理中文编码
        try:
            if src_lang in ['zh', 'en']:
                target_path = en_srt_path if src_lang == 'zh' else zh_srt_path
                with open(target_path, 'w', encoding='utf-8-sig') as f:  # 使用utf-8-sig
                    for i, seg in enumerate(result['segments'], 1):
                        original_text = convert(seg['text'], 'zh-cn') if src_lang == 'zh' else seg['text']
                        try:
                            translated_text = translator.translate(
                                original_text,
                                src_lang,
                                'en' if src_lang == 'zh' else 'zh'
                            )
                            # 确保翻译后的文本是unicode字符串
                            if isinstance(translated_text, bytes):
                                translated_text = translated_text.decode('utf-8')
                            f.write(f"{i}\n")
                            f.write(f"{seconds_to_hmsm(seg['start'])} --> {seconds_to_hmsm(seg['end'])}\n")
                            f.write(f"{translated_text}\n\n")
                        except Exception as e:
                            print(f"翻译段落 {i} 失败: {str(e)}")
                            # 写入原始文本作为回退
                            f.write(f"{i}\n")
                            f.write(f"{seconds_to_hmsm(seg['start'])} --> {seconds_to_hmsm(seg['end'])}\n")
                            f.write(f"{original_text}\n\n")
        except Exception as e:
            print(f"创建翻译字幕失败: {str(e)}")

        # 输出处理时间
        duration = datetime.datetime.now() - start_time
        print(f"处理完成，耗时: {duration.total_seconds():.1f}秒")


if __name__ == "__main__":
    main()