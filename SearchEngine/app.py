from datetime import timedelta
from flask import Flask, render_template, request, session, jsonify
import pandas as pd
from search import weighted_search, search_bilibili
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.permanent_session_lifetime = timedelta(days=7)

# 临时 CSV 文件路径
TEMP_CSV_PATH = "temp_search_results.csv"

@app.before_request
def init_favorites():
    if 'favorites' not in session:
        session.permanent = True
        session['favorites'] = []

@app.route('/favorites')
def show_favorites():
    favorites = session.get('favorites', [])
    total = len(favorites)
    paginated_favorites = favorites[:20]
    return render_template('favorite.html', favorites=paginated_favorites, total=total)

@app.route('/favorites_page', methods=['POST'])
def favorites_page():
    try:
        data = request.json
        page = int(data.get('page', 1))
        items_per_page = int(data.get('items_per_page', 20))

        favorites = session.get('favorites', [])
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
    video_data = request.json
    video_info = {
        "bvid": str(video_data['bvid']),
        "title": str(video_data['title']),
        "heat": float(video_data['heat'])
    }
    if not any(item['bvid'] == video_info['bvid'] for item in session['favorites']):
        session['favorites'].append(video_info)
        session.modified = True
    return {"status": "success"}

@app.route('/remove_favorite', methods=['POST'])
def remove_favorite():
    try:
        data = request.json
        bvid = data.get('bvid')
        if not bvid:
            return jsonify({"error": "缺少 bvid 参数"})

        favorites = session.get('favorites', [])
        session['favorites'] = [item for item in favorites if item['bvid'] != bvid]
        session.modified = True
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": f"取消收藏失败：{str(e)}"})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    keywords = request.form.get('keywords', '')
    keyword_list = [k.strip() for k in keywords.split('#') if k.strip()]
    try:
        if os.path.exists(TEMP_CSV_PATH):
            os.remove(TEMP_CSV_PATH)
        search_bilibili(keyword_list, max_page=5, out_file=TEMP_CSV_PATH)
        if not os.path.exists(TEMP_CSV_PATH):
            return render_template('result.html', error="爬虫未生成数据，请稍后再试")
        df = pd.read_csv(TEMP_CSV_PATH)
        if df.empty:
            return render_template('result.html', error="爬虫数据为空，请尝试其他关键词")
        results = weighted_search(query=keyword_list, df=df.copy(), top_n=5000)
        result_data = results.to_dict(orient='records')
        total = len(result_data)
        paginated_results = result_data[:20]
        favorites_bvid = [item['bvid'] for item in session.get('favorites', [])]
        return render_template(
            'result.html',
            keywords=keywords,
            results=paginated_results,
            total=total,
            favorites_bvid=favorites_bvid
        )
    except Exception as e:
        return render_template('result.html', error=f"搜索失败：{str(e)}")

@app.route('/search_page', methods=['POST'])
def search_page():
    try:
        data = request.json
        keywords = data.get('keywords', '')
        page = int(data.get('page', 1))
        items_per_page = int(data.get('items_per_page', 20))
        keyword_list = [k.strip() for k in keywords.split('#') if k.strip()]

        if not keywords:
            return jsonify({"error": "关键词为空"})

        if not os.path.exists(TEMP_CSV_PATH):
            return jsonify({"error": "数据文件不存在，请重新搜索"})

        df = pd.read_csv(TEMP_CSV_PATH)
        if df.empty:
            return jsonify({"error": "数据文件为空，请重新搜索"})

        results = weighted_search(query=keyword_list, df=df.copy(), top_n=5000)
        result_data = results.to_dict(orient='records')

        start = (page - 1) * items_per_page
        end = start + items_per_page
        paginated_results = result_data[start:end]

        favorites_bvid = [item['bvid'] for item in session.get('favorites', [])]
        for item in paginated_results:
            item['is_favorited'] = item['bvid'] in favorites_bvid

        return jsonify({
            "results": paginated_results,
            "total": len(result_data)
        })
    except Exception as e:
        return jsonify({"error": f"分页处理失败：{str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)