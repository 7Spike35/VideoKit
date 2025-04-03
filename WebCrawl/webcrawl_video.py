import requests
import xml.etree.ElementTree as ET
import pandas as pd
import re

# UA伪装
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

video_url = input("输入视频的url:")
response = requests.get(video_url, headers=headers)
html = response.text


# 使用正则表达式提取 cid
cid_pattern = r'"cid":(\d+)'
cid_match = re.search(cid_pattern, html)
if cid_match:
    cid = cid_match.group(1)
    print(f'cid: {cid}')
else:
    print('未找到 cid')


# 下面获取弹幕网站
comments_url = 'https://comment.bilibili.com/%s.xml' % cid

# 发送请求
response = requests.get(comments_url, headers=headers)
print(response)
xml = ET.fromstring(response.content)

# 解析数据
dm = xml.findall(".//d")
dm_list = [d.text for d in dm]
print(dm_list)

# 把列表转换成 dataframe
dm_df = pd.DataFrame(dm_list, columns=['comment'])
print(dm_df)

# 存到本地
dm_df.to_csv('comments.csv', encoding='utf_8_sig')