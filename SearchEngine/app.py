from flask import Flask, render_template, request, session, jsonify, flash, redirect, url_for
import pandas as pd
from search import weighted_search, search_bilibili
from webcrawl_video import get_comments_csv
from analysis import f
import os
import requests
from datetime import timedelta
import time
import io
import sys
import re
import csv
import json
from sqlmodel import SQLModel, create_engine, Session, select
from models import User
import bcrypt

# 解决编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.permanent_session_lifetime = timedelta(days=7)

# 数据库初始化
DATABASE_URL = "sqlite:///db.sqlite"
engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(engine)

# 全局收藏（共享）
FAVORITES_FILE = "favorites.json"
global_favorites = {'video_favorites': [], 'live_favorites': []}

# 加载收藏
def load_favorites():
    global global_favorites
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            global_favorites = json.load(f)
    else:
        global_favorites = {'video_favorites': [], 'live_favorites': []}

# 保存收藏
def save_favorites():
    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(global_favorites, f, ensure_ascii=False, indent=2)

# 初始化收藏
load_favorites()

# 临时 CSV 文件路径
TEMP_CSV_PATH = "temp_search_results.csv"
TEMP_LIVE_CSV_PATH = "temp_live_results.csv"
COMMENTS_CSV_PATH = "comments.csv"
DANMU_DIR = "static/danmu"
if not os.path.exists(DANMU_DIR):
    os.makedirs(DANMU_DIR)

# B 站直播 API
BILIBILI_LIVE_API = "https://api.live.bilibili.com/room/v1/Room/get_info"

class Danmu:
    def __init__(self, room_id, output_path):
        self.url = 'https://api.live.bilibili.com/xlive/web-room/v1/dM/gethistory'
        self.headers = {
            'Host': 'api.live.bilibili.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:78.0) Gecko/20100101 Firefox/78.0',
        }
        self.data = {
            'roomid': room_id,
            'csrf_token': '',
            'csrf': '',
            'visit_id': '',
        }
        self.danmu_seen = set()
        self.output_path = output_path

    def get_danmu(self):
        try:
            response = requests.post(url=self.url, headers=self.headers, data=self.data)
            response.raise_for_status()
            html = response.json()
            if 'data' in html and 'room' in html['data']:
                danmu_list = html['data']['room']
                with open(self.output_path, mode="a", encoding="utf-8", newline="") as file:
                    writer = csv.writer(file)
                    for content in danmu_list:
                        nickname = content.get('nickname', '未知用户')
                        text = content.get('text', '')
                        timeline = content.get('timeline', '')
                        msg_tuple = (timeline, nickname, text)
                        if msg_tuple not in self.danmu_seen:
                            self.danmu_seen.add(msg_tuple)
                            writer.writerow([timeline, nickname, text])
        except Exception as e:
            print(f"获取直播间 {self.data['roomid']} 弹幕时出错: {e}")

@app.before_request
def init_session():
    if 'live_status_cache' not in session:
        session.permanent = True
        session['live_status_cache'] = {'timestamp': 0, 'live_count': 0, 'status': {}}

@app.context_processor
def inject_user():
    user = session.get('username', None)
    return {'current_user': user}

@app.context_processor
def inject_live_count():
    cache = session.get('live_status_cache', {'timestamp': 0, 'live_count': 0, 'status': {}})
    current_time = time.time()
    cache_timeout = 60
    live_count = cache['live_count']
    live_status = cache['status']

    if current_time - cache['timestamp'] > cache_timeout or not live_status:
        live_favorites = global_favorites.get('live_favorites', [])
        live_count = 0
        if live_favorites:
            room_ids = [item['id'] for item in live_favorites]
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            for room_id in room_ids:
                try:
                    response = requests.get(
                        BILIBILI_LIVE_API,
                        params={'room_id': room_id},
                        headers=headers,
                        timeout=5
                    )
                    response.raise_for_status()
                    result = response.json()
                    if result.get('code') == 0:
                        is_live = result['data']['live_status'] == 1
                        live_status[room_id] = {'is_live': is_live}
                        if is_live:
                            live_count += 1
                    else:
                        live_status[room_id] = {'is_live': False}
                except Exception:
                    live_status[room_id] = {'is_live': False}

        session['live_status_cache'] = {
            'timestamp': current_time,
            'live_count': live_count,
            'status': live_status
        }
        session.modified = True

    return {'live_count': live_count}

@app.route('/register', methods=['POST'])
def register():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        repeat_password = request.form.get('repeat_password')

        if not username or not password:
            return jsonify({"status": "error", "error": "用户名和密码不能为空"})
        if password != repeat_password:
            return jsonify({"status": "error", "error": "两次密码不一致"})

        with Session(engine) as db:
            if db.exec(select(User).where(User.username == username)).first():
                return jsonify({"status": "error", "error": "用户名已存在"})

            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user = User(username=username, password=hashed_password)
            db.add(user)
            db.commit()

        return jsonify({"status": "success", "message": "注册成功，请登录"})
    except Exception as e:
        return jsonify({"status": "error", "error": f"注册失败：{str(e)}"})

@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return jsonify({"status": "error", "error": "用户名和密码不能为空"})

        with Session(engine) as db:
            user = db.exec(select(User).where(User.username == username)).first()
            if not user:
                return jsonify({"status": "error", "error": "用户不存在"})
            if not bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
                return jsonify({"status": "error", "error": "密码错误"})

        session['username'] = username
        session.modified = True
        return jsonify({"status": "success", "message": "登录成功"})
    except Exception as e:
        return jsonify({"status": "error", "error": f"登录失败：{str(e)}"})

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/trigger_crawl', methods=['POST'])
def trigger_crawl():
    try:
        live_favorites = global_favorites.get('live_favorites', [])
        live_status = session.get('live_status_cache', {'status': {}})['status']
        last_crawl = session.get('last_crawl_time', 0)
        current_time = time.time()

        if current_time - last_crawl < 60:
            return jsonify({"status": "success", "message": "爬取冷却中，请稍后"})

        crawled = 0
        for item in live_favorites:
            room_id = item['id']
            if live_status.get(room_id, {'is_live': False})['is_live']:
                output_path = os.path.join(DANMU_DIR, f"live_comments_{room_id}.csv")
                with open(output_path, mode="w", encoding="utf-8", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow(["时间", "用户", "弹幕内容"])
                danmu = Danmu(room_id, output_path)
                for _ in range(10):
                    danmu.get_danmu()
                    time.sleep(0.5)
                crawled += 1

        session['last_crawl_time'] = current_time
        session.modified = True
        return jsonify({"status": "success", "message": f"爬取 {crawled} 个直播间"})
    except Exception as e:
        return jsonify({"error": f"爬取失败：{str(e)}"})

@app.route('/live_analysis')
def live_analysis():
    live_favorites = global_favorites.get('live_favorites', [])
    live_status = session.get('live_status_cache', {'status': {}})['status']
    analysis_results = []

    for item in live_favorites:
        room_id = item['id']
        if live_status.get(room_id, {'is_live': False})['is_live']:
            csv_path = os.path.join(DANMU_DIR, f"live_comments_{room_id}.csv")
            if os.path.exists(csv_path):
                try:
                    df = pd.read_csv(csv_path)
                    if not df.empty:
                        df.columns = ['time', 'user', 'comment']
                        df.to_csv(csv_path, index=False)
                        result = f(csv_path)
                        analysis_results.append({
                            'room_id': room_id,
                            'title': item['title'],
                            'analysis': result
                        })
                except Exception as e:
                    analysis_results.append({
                        'room_id': room_id,
                        'title': item['title'],
                        'analysis': {'error': f"分析失败：{str(e)}"}
                    })
            else:
                analysis_results.append({
                    'room_id': room_id,
                    'title': item['title'],
                    'analysis': {'error': '弹幕数据未爬取'}
                })

    return render_template('live_analysis.html', results=analysis_results)

@app.route('/check_live_status', methods=['POST'])
def check_live_status():
    try:
        data = request.json
        room_ids = data.get('room_ids', [])
        if not room_ids:
            return jsonify({"error": "未提供房间 ID"})

        live_status = {}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        for room_id in room_ids:
            try:
                response = requests.get(
                    BILIBILI_LIVE_API,
                    params={'room_id': room_id},
                    headers=headers,
                    timeout=5
                )
                response.raise_for_status()
                result = response.json()
                if result.get('code') == 0:
                    status = result['data']['live_status']
                    live_status[room_id] = {'is_live': status == 1}
                else:
                    live_status[room_id] = {'is_live': False, 'error': result.get('msg', 'API 错误')}
            except Exception as e:
                live_status[room_id] = {'is_live': False, 'error': str(e)}

        return jsonify({"status": "success", "live_status": live_status})
    except Exception as e:
        return jsonify({"error": f"检查直播状态失败：{str(e)}"})

@app.route('/favorites')
def show_favorites():
    video_favorites = global_favorites.get('video_favorites', [])
    live_favorites = global_favorites.get('live_favorites', [])
    video_total = len(video_favorites)
    live_total = len(live_favorites)
    paginated_video_favorites = video_favorites[:10]
    paginated_live_favorites = live_favorites[:10]

    live_status = session.get('live_status_cache', {'status': {}})['status']
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for item in paginated_live_favorites:
        room_id = item['id']
        if room_id not in live_status:
            try:
                response = requests.get(
                    BILIBILI_LIVE_API,
                    params={'room_id': room_id},
                    headers=headers,
                    timeout=5
                )
                response.raise_for_status()
                result = response.json()
                if result.get('code') == 0:
                    live_status[room_id] = {'is_live': result['data']['live_status'] == 1}
                else:
                    live_status[room_id] = {'is_live': False}
            except Exception:
                live_status[room_id] = {'is_live': False}
        item['is_live'] = live_status.get(room_id, {'is_live': False})['is_live']

    return render_template(
        'favorite.html',
        video_favorites=paginated_video_favorites,
        live_favorites=paginated_live_favorites,
        video_total=video_total,
        live_total=live_total
    )

@app.route('/favorites_page', methods=['POST'])
def favorites_page():
    try:
        data = request.json
        page = int(data.get('page', 1))
        items_per_page = int(data.get('items_per_page', 10))
        fav_type = data.get('type', 'video')

        if fav_type == 'video':
            favorites = global_favorites.get('video_favorites', [])
        else:
            favorites = global_favorites.get('live_favorites', [])
        total = len(favorites)

        start = (page - 1) * items_per_page
        end = start + items_per_page
        paginated_favorites = favorites[start:end]

        if fav_type == 'live' and paginated_favorites:
            live_status = session.get('live_status_cache', {'status': {}})['status']
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            for item in paginated_favorites:
                room_id = item['id']
                if room_id not in live_status:
                    try:
                        response = requests.get(
                            BILIBILI_LIVE_API,
                            params={'room_id': room_id},
                            headers=headers,
                            timeout=5
                        )
                        response.raise_for_status()
                        result = response.json()
                        if result.get('code') == 0:
                            live_status[room_id] = {'is_live': result['data']['live_status'] == 1}
                        else:
                            live_status[room_id] = {'is_live': False}
                    except Exception:
                        live_status[room_id] = {'is_live': False}
                item['is_live'] = live_status.get(room_id, {'is_live': False})['is_live']

        return jsonify({
            "favorites": paginated_favorites,
            "total": total
        })
    except Exception as e:
        return jsonify({"error": f"分页处理失败：{str(e)}"})

@app.route('/add_favorite', methods=['POST'])
def add_favorite():
    data = request.json
    id = str(data['id'])
    fav_type = data.get('type', 'video')
    favorite_info = {
        "id": id,
        "title": str(data['title']),
        "heat": float(data['heat'])
    }

    if fav_type == 'video':
        favorites = global_favorites.get('video_favorites', [])
        if not any(item['id'] == id for item in favorites):
            favorites.append(favorite_info)
            global_favorites['video_favorites'] = favorites
    else:
        favorites = global_favorites.get('live_favorites', [])
        if not any(item['id'] == id for item in favorites):
            favorites.append(favorite_info)
            global_favorites['live_favorites'] = favorites

    save_favorites()
    session['live_status_cache'] = {'timestamp': 0, 'live_count': 0, 'status': {}}
    session.modified = True

    return {"status": "success"}

@app.route('/remove_favorite', methods=['POST'])
def remove_favorite():
    try:
        data = request.json
        id = data.get('id')
        fav_type = data.get('type', 'video')
        if not id:
            return jsonify({"error": "缺少 ID 参数"})

        if fav_type == 'video':
            favorites = global_favorites.get('video_favorites', [])
            global_favorites['video_favorites'] = [item for item in favorites if item['id'] != id]
        else:
            favorites = global_favorites.get('live_favorites', [])
            global_favorites['live_favorites'] = [item for item in favorites if item['id'] != id]

        save_favorites()
        session['live_status_cache'] = {'timestamp': 0, 'live_count': 0, 'status': {}}
        session.modified = True

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": f"取消收藏失败：{str(e)}"})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        keywords = request.form.get('keywords', '')
        session['last_keywords'] = keywords
        session.modified = True
    else:
        keywords = session.get('last_keywords', '')

    keyword_list = [k.strip() for k in keywords.split('#') if k.strip()]
    try:
        if not keyword_list:
            return render_template('result.html', error="无关键词，请输入搜索内容")

        if os.path.exists(TEMP_CSV_PATH):
            os.remove(TEMP_CSV_PATH)
        if os.path.exists(TEMP_LIVE_CSV_PATH):
            os.remove(TEMP_LIVE_CSV_PATH)

        search_bilibili(keyword_list, max_page=5, video_out_file=TEMP_CSV_PATH, live_out_file=TEMP_LIVE_CSV_PATH)

        if not os.path.exists(TEMP_CSV_PATH):
            video_error = "视频爬虫未生成数据，请稍后再试"
            video_results = []
            video_total = 0
        else:
            df = pd.read_csv(TEMP_CSV_PATH)
            if df.empty:
                video_error = "视频爬虫数据为空，请尝试其他关键词"
                video_results = []
                video_total = 0
            else:
                video_error = None
                results = weighted_search(query=keyword_list, df=df.copy(), top_n=5000)
                video_results = results.to_dict(orient='records')
                video_total = len(video_results)

        if not os.path.exists(TEMP_LIVE_CSV_PATH):
            live_error = "直播爬虫未生成数据，请稍后再试"
            live_results = []
            live_total = 0
        else:
            live_df = pd.read_csv(TEMP_LIVE_CSV_PATH)
            if live_df.empty:
                live_error = "直播爬虫数据为空，请尝试其他关键词"
                live_results = []
                live_total = 0
            else:
                live_error = None
                live_results = live_df.to_dict(orient='records')
                live_total = len(live_results)

        if video_error and live_error:
            return render_template('result.html', error=f"{video_error}；{live_error}")

        favorites_bvid = [item['id'] for item in global_favorites.get('video_favorites', [])]
        favorites_room_id = [item['id'] for item in global_favorites.get('live_favorites', [])]
        return render_template(
            'result.html',
            keywords=keywords,
            video_results=video_results[:10],
            live_results=live_results[:10],
            video_total=video_total,
            live_total=live_total,
            favorites_bvid=favorites_bvid,
            favorites_room_id=favorites_room_id
        )
    except Exception as e:
        return render_template('result.html', error=f"搜索失败：{str(e)}")

@app.route('/search_page', methods=['POST'])
def search_page():
    try:
        data = request.json
        keywords = data.get('keywords', '')
        page = int(data.get('page', 1))
        items_per_page = int(data.get('items_per_page', 10))
        result_type = data.get('type', 'video')

        keyword_list = [k.strip() for k in keywords.split('#') if k.strip()]

        if not keywords:
            return jsonify({"error": "关键词为空"})

        if result_type == 'video':
            if not os.path.exists(TEMP_CSV_PATH):
                return jsonify({"error": "视频数据文件不存在，请重新搜索"})
            df = pd.read_csv(TEMP_CSV_PATH)
            if df.empty:
                return jsonify({"error": "视频数据文件为空，请重新搜索"})
            results = weighted_search(query=keyword_list, df=df.copy(), top_n=5000)
            result_data = results.to_dict(orient='records')
            favorites = global_favorites.get('video_favorites', [])
        else:
            if not os.path.exists(TEMP_LIVE_CSV_PATH):
                return jsonify({"error": "直播数据文件不存在，请重新搜索"})
            df = pd.read_csv(TEMP_LIVE_CSV_PATH)
            if df.empty:
                return jsonify({"error": "直播数据文件为空，请重新搜索"})
            result_data = df.to_dict(orient='records')
            favorites = global_favorites.get('live_favorites', [])

        start = (page - 1) * items_per_page
        end = start + items_per_page
        paginated_results = result_data[start:end]

        favorites_ids = [item['id'] for item in favorites]
        for item in paginated_results:
            item['is_favorited'] = (item['bvid'] if result_type == 'video' else str(item['room_id'])) in favorites_ids

        return jsonify({
            "results": paginated_results,
            "total": len(result_data)
        })
    except Exception as e:
        return jsonify({"error": f"分页处理失败：{str(e)}"})

@app.route('/analyze/<bvid>')
def analyze(bvid):
    try:
        if not bvid or not isinstance(bvid, str):
            return render_template('analysis.html', error="无效的BVID")

        csv_result = get_comments_csv(bvid)
        if csv_result is None:
            return render_template('analysis.html', error="无法获取弹幕数据")
        elif isinstance(csv_result, pd.DataFrame):
            if csv_result.empty:
                return render_template('analysis.html', error="弹幕数据为空")
            csv_result.to_csv(COMMENTS_CSV_PATH, index=False, encoding='utf-8')
        else:
            return render_template('analysis.html', error="弹幕数据格式错误")

        analysis_result = f(COMMENTS_CSV_PATH)
        if 'error' in analysis_result:
            return render_template('analysis.html', error=analysis_result['error'])

        return render_template('analysis.html', analysis=analysis_result, bvid=bvid,
                               keywords=session.get('last_keywords', ''))
    except Exception as e:
        return render_template('analysis.html', error=f"分析失败：{str(e)}")

if __name__ == '__main__':
    app.run(debug=True)