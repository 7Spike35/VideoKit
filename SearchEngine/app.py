from datetime import timedelta
from flask import Flask, render_template, request, session, jsonify
import pandas as pd
from search import weighted_search, search_bilibili
from webcrawl_video import get_comments_csv
from analysis import f
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.permanent_session_lifetime = timedelta(days=7)

# 临时 CSV 文件路径
TEMP_CSV_PATH = "temp_search_results.csv"
TEMP_LIVE_CSV_PATH = "temp_live_results.csv"
COMMENTS_CSV_PATH = "comments.csv"


@app.before_request
def init_favorites():
    if 'video_favorites' not in session:
        session.permanent = True
        session['video_favorites'] = []
    if 'live_favorites' not in session:
        session.permanent = True
        session['live_favorites'] = []


@app.route('/favorites')
def show_favorites():
    video_favorites = session.get('video_favorites', [])
    live_favorites = session.get('live_favorites', [])
    video_total = len(video_favorites)
    live_total = len(live_favorites)
    paginated_video_favorites = video_favorites[:10]
    paginated_live_favorites = live_favorites[:10]
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
        fav_type = data.get('type', 'video')  # 'video' or 'live'

        if fav_type == 'video':
            favorites = session.get('video_favorites', [])
        else:
            favorites = session.get('live_favorites', [])
        total = len(favorites)

        start = (page - 1) * items_per_page
        end = start + items_per_page
        paginated_favorites = favorites[start:end]

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
        favorites = session.get('video_favorites', [])
        if not any(item['id'] == id for item in favorites):
            favorites.append(favorite_info)
            session['video_favorites'] = favorites
            session.modified = True
    else:  # live
        favorites = session.get('live_favorites', [])
        if not any(item['id'] == id for item in favorites):
            favorites.append(favorite_info)
            session['live_favorites'] = favorites
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
            favorites = session.get('video_favorites', [])
            session['video_favorites'] = [item for item in favorites if item['id'] != id]
        else:  # live
            favorites = session.get('live_favorites', [])
            session['live_favorites'] = [item for item in favorites if item['id'] != id]

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

        # 删除旧的临时文件
        if os.path.exists(TEMP_CSV_PATH):
            os.remove(TEMP_CSV_PATH)
        if os.path.exists(TEMP_LIVE_CSV_PATH):
            os.remove(TEMP_LIVE_CSV_PATH)

        # 爬取视频和直播数据
        search_bilibili(keyword_list, max_page=5, video_out_file=TEMP_CSV_PATH, live_out_file=TEMP_LIVE_CSV_PATH)

        # 处理视频结果
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

        # 处理直播结果
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

        # 如果两者都出错，返回错误页面
        if video_error and live_error:
            return render_template('result.html', error=f"{video_error}；{live_error}")

        favorites_bvid = [item['id'] for item in session.get('video_favorites', [])]
        favorites_room_id = [item['id'] for item in session.get('live_favorites', [])]
        return render_template(
            'result.html',
            keywords=keywords,
            video_results=video_results[:10],
            video_total=video_total,
            live_results=live_results[:10],
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
        result_type = data.get('type', 'video')  # 'video' or 'live'

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
            favorites = session.get('video_favorites', [])
        else:  # live
            if not os.path.exists(TEMP_LIVE_CSV_PATH):
                return jsonify({"error": "直播数据文件不存在，请重新搜索"})
            df = pd.read_csv(TEMP_LIVE_CSV_PATH)
            if df.empty:
                return jsonify({"error": "直播数据文件为空，请重新搜索"})
            result_data = df.to_dict(orient='records')
            favorites = session.get('live_favorites', [])

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

        # 获取弹幕数据
        csv_result = get_comments_csv(bvid)
        if csv_result is None:
            return render_template('analysis.html', error="无法获取弹幕数据")
        elif isinstance(csv_result, pd.DataFrame):
            if csv_result.empty:
                return render_template('analysis.html', error="弹幕数据为空")
            csv_result.to_csv(COMMENTS_CSV_PATH, index=False, encoding='utf-8')
        else:
            return render_template('analysis.html', error="弹幕数据格式错误")

        # 调用分析函数
        analysis_result = f(COMMENTS_CSV_PATH)
        if 'error' in analysis_result:
            return render_template('analysis.html', error=analysis_result['error'])

        return render_template('analysis.html', analysis=analysis_result, bvid=bvid,
                               keywords=session.get('last_keywords', ''))
    except Exception as e:
        return render_template('analysis.html', error=f"分析失败：{str(e)}")


if __name__ == '__main__':
    app.run(debug=True)