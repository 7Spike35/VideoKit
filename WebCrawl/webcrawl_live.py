import requests
import time
import io
import sys
import re
import csv

# 解决编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 直播间 URL
url = input("请输入直播间url:")  # 示例: 'https://live.bilibili.com/21396545'
roomid = re.search(r'live.bilibili.com/(\d+)', url).group(1)


class Danmu:
    def __init__(self):
        # 弹幕 API URL
        self.url = 'https://api.live.bilibili.com/xlive/web-room/v1/dM/gethistory'
        # 请求头
        self.headers = {
            'Host': 'api.live.bilibili.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:78.0) Gecko/20100101 Firefox/78.0',
        }
        # 定义 POST 传递的参数
        self.data = {
            'roomid': roomid,
            'csrf_token': '',
            'csrf': '',
            'visit_id': '',
        }
        # 存储已获取的弹幕，避免重复
        self.danmu_seen = set()

    def get_danmu(self):
        try:
            # 获取直播间弹幕
            response = requests.post(url=self.url, headers=self.headers, data=self.data)
            response.raise_for_status()  # 检查请求是否成功
            html = response.json()

            # 解析弹幕列表
            if 'data' in html and 'room' in html['data']:
                danmu_list = html['data']['room']
                with open("live_comments.csv", mode="a", encoding="utf-8", newline="") as file:
                    writer = csv.writer(file)
                    for content in danmu_list:
                        # 获取昵称
                        nickname = content.get('nickname', '未知用户')
                        # 获取发言
                        text = content.get('text', '')
                        # 获取发言时间
                        timeline = content.get('timeline', '')

                        # 组合唯一键值，防止重复弹幕
                        msg_tuple = (timeline, nickname, text)
                        if msg_tuple not in self.danmu_seen:
                            self.danmu_seen.add(msg_tuple)
                            writer.writerow([timeline, nickname, text])
                            print(timeline, nickname + ':', text)
        except Exception as e:
            print("获取弹幕时出错:", e)


if __name__ == '__main__':
    # 创建 Danmu 实例
    bDanmu = Danmu()

    # 写入 CSV 文件表头
    with open("live_comments.csv", mode="w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["时间", "用户", "弹幕内容"])

    # 循环获取弹幕
    for _ in range(50):
        time.sleep(0.5)  # 适当增加爬取间隔，减少重复
        bDanmu.get_danmu()
