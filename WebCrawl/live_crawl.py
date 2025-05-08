import time
import requests
import pandas as pd


def get_room_info(room_id, headers):
    """获取直播间详细信息（如人气）"""
    url = f'https://api.live.bilibili.com/room/v1/Room/get_info?room_id={room_id}'
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            r.encoding = 'utf-8'
            j_data = r.json()
            if j_data.get('code') == 0:
                return j_data.get('data', {})
            print(f'房间{room_id}信息获取失败：{j_data.get("message")}')
        return {}
    except Exception as e:
        print(f'获取房间{room_id}信息失败：{e}')
        return {}


def search_bilibili(keyword, max_page, out_file):
    all_data = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36',
        'Cookie': "buvid3=A05467BA-4CA7-FC5D-32B9-69CEEA5A9DBD83649infoc; b_nut=1723300982; buvid4=A73D3B1D-1B46-E3AA-87CC-8A88E1B294E083649-024081014-EJpV8JZlT8Ymau483lFaEw%3D%3D; _uuid=A0A75BAA-509E-6835-1262-8C01B161B2B183241infoc; DedeUserID=297551493; DedeUserID__ckMd5=a1f51c530f60103c; rpdid=|(J~RlluYlJ~0J'u~kJJ|u|u); header_theme_version=CLOSE; enable_web_push=DISABLE; fingerprint=65aaeff10f5af363b847547a0601e342; buvid_fp_plain=undefined; buvid_fp=65aaeff10f5af363b847547a0601e342; LIVE_BUVID=AUTO3817409827308858; enable_feed_channel=ENABLE; PVID=2; CURRENT_FNVAL=4048; bp_t_offset_297551493=1063149734568394752; b_lsid=B71A6A10C_196AE9BF807; bsource=search_bing; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDY5NDUzODAsImlhdCI6MTc0NjY4NjEyMCwicGx0IjotMX0.E6OwylKaJfaz-ACZcd_yMFfluICRSEIqNhiQTEruYGM; bili_ticket_expires=1746945320; SESSDATA=21e61b58%2C1762238181%2C0773d%2A52CjCIhVar0tv7LZ2DWtXReRIcaJ4SPDd84kI89Gunp48N_FwvZKnBs-sy08a1SdSpWQ0SVjkwc2RsZndKdTFNNm80T1hlSXlLZHRqbWlOZTBRRUgtLVY0WWY1NEJ4R1dlM0FaWDU3Mms1UWlFTXF3eUc4blNYcXhPXzlQQWtyNVBJdGdsY0t2M1BBIIEC; bili_jct=f96d246716b3b6e4d74ebd910462fd80; sid=n6g95skq; home_feed_column=4; browser_resolution=1100-1157"
    }

    for page in range(1, max_page + 1):
        print(f'正在爬取第{page}页')
        url = 'https://api.bilibili.com/x/web-interface/search/type'
        params = {'search_type': 'live', 'keyword': keyword, 'page': page, 'order': 'online'}

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                print(f'请求失败，状态码：{response.status_code}')
                continue
            response.encoding = 'utf-8'
            j_data = response.json()
            print("API完整响应:", j_data)

            if j_data.get('code') != 0:
                print(f'API返回错误：{j_data.get("message")}')
                continue

            data = j_data.get('data', {})
            print("data字段:", data)

            # 修改这里：检查result字段的结构
            result = data.get('result', {})

            if isinstance(result, dict):
                # 如果是字典，尝试获取live_room字段
                room_list = result.get('live_room', [])
                if not isinstance(room_list, list):
                    print('live_room字段不是列表:', room_list)
                    room_list = []
            elif isinstance(result, list):
                # 如果是列表，直接使用
                room_list = result
            else:
                print('result字段不是列表也不是字典:', result)
                room_list = []

            print(f'本页获取到{len(room_list)}个直播间')
            for item in room_list:
                all_data.append({
                    'room_id': item.get('roomid', 'N/A'),
                    '标题': item.get('title', '无标题'),
                    '主播': item.get('uname', '未知'),
                    '人气': item.get('online', 0),
                    '分类': item.get('area_v2_name', '未知分类')
                })

            time.sleep(1)
        except Exception as e:
            print(f'请求失败: {e}')
            continue

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(out_file, index=False, encoding='utf_8_sig')
        print(f'数据已保存到{out_file}')
        print("保存的数据示例:")
        print(df.head())
    else:
        print('未获取到有效数据')


if __name__ == "__main__":
    search_bilibili('lol', 2, 'live_data.csv')