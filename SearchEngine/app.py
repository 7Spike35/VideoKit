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
    return render_template('favorite.html', favorites=session['favorites'])

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    keywords = request.form.get('keywords', '')
    keyword_list = [k.strip() for k in keywords.split('#') if k.strip()]
    try:
        search_bilibili(keyword_list, max_page=5, out_file=TEMP_CSV_PATH)
        if not os.path.exists(TEMP_CSV_PATH):
            return render_template('result.html', error="爬虫未生成数据，请稍后再试")
        df = pd.read_csv(TEMP_CSV_PATH)
        results = weighted_search(query=keyword_list, df=df.copy(), top_n=5000)
        result_data = results.to_dict(orient='records')
        total = len(result_data)
        # 初始显示第一页（前 20 条）
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
        return render_template('result.html', error=str(e))

@app.route('/search_page', methods=['POST'])
def search_page():
    try:
        data = request.json
        keywords = data.get('keywords', '')
        page = int(data.get('page', 1))
        items_per_page = int(data.get('items_per_page', 20))
        keyword_list = [k.strip() for k in keywords.split('#') if k.strip()]

        # 读取爬虫生成的 CSV
        if not os.path.exists(TEMP_CSV_PATH):
            return jsonify({"error": "数据文件不存在，请重新搜索"})

        df = pd.read_csv(TEMP_CSV_PATH)
        results = weighted_search(query=keyword_list, df=df.copy(), top_n=5000)
        result_data = results.to_dict(orient='records')

        # 计算分页
        start = (page - 1) * items_per_page
        end = start + items_per_page
        paginated_results = result_data[start:end]

        # 添加收藏状态
        favorites_bvid = [item['bvid'] for item in session.get('favorites', [])]
        for item in paginated_results:
            item['is_favorited'] = item['bvid'] in favorites_bvid

        return jsonify({
            "results": paginated_results,
            "total": len(result_data)
        })
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)