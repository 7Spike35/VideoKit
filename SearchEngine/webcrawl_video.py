import requests
import xml.etree.ElementTree as ET
import pandas as pd
import re

def get_comments_csv(bvid):
    """
    从B站视频的BVID提取弹幕并返回DataFrame。

    参数:
        bvid (str): B站视频的BVID（例如 'BV1Sx411o78N'）

    返回:
        pd.DataFrame: 包含弹幕的DataFrame，带有'comment'列。
        None: 如果提取失败。
    """
    try:
        # 构造视频URL
        video_url = f"https://www.bilibili.com/video/{bvid}"
        print(f"Fetching video page: {video_url}")  # Debug log

        # UA伪装
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # 获取视频页面
        response = requests.get(video_url, headers=headers)
        response.raise_for_status()  # 检查请求是否成功
        html = response.text

        # 使用正则表达式提取 cid
        cid_pattern = r'"cid":(\d+)'
        cid_match = re.search(cid_pattern, html)

        if not cid_match:
            print("未找到 cid，请检查BVID是否正确")
            return None

        cid = cid_match.group(1)
        print(f'Fetched cid: {cid}')  # Debug log

        # 构造弹幕链接
        comments_url = f"https://comment.bilibili.com/{cid}.xml"
        print(f"Fetching comments from: {comments_url}")  # Debug log

        # 发送请求获取弹幕数据
        response = requests.get(comments_url, headers=headers)
        response.raise_for_status()  # 检查请求是否成功

        # 解析XML
        try:
            xml = ET.fromstring(response.content)
        except ET.ParseError:
            print("XML解析失败，请检查网络连接或稍后重试")
            return None

        # 提取弹幕内容
        dm = xml.findall(".//d")
        if not dm:
            print("未找到弹幕数据")
            return None

        dm_list = [d.text for d in dm]
        print(f"Fetched {len(dm_list)} comments")  # Debug log

        # 转换为DataFrame
        dm_df = pd.DataFrame(dm_list, columns=['comment'])

        return dm_df

    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {e}")
        print("请检查网络连接或BVID的合法性")
        return None
    except Exception as e:
        print(f"发生错误: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    bvid = "BV1Sx411o78N"  # 示例BVID
    df = get_comments_csv(bvid)
    if df is not None:
        print(f"Fetched DataFrame:\n{df}")
    else:
        print("Failed to fetch comments")