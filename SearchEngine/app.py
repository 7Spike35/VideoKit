from datetime import timedelta

from flask import Flask, render_template, request, session
import pandas as pd
from search import weighted_search

app = Flask(__name__)

# 预加载数据
CSV_PATH = r".\file\bilibili_result.csv"
df = pd.read_csv(CSV_PATH)

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.permanent_session_lifetime = timedelta(days=7)

@app.before_request
def init_favorites():
    # 只在session不存在时初始化
    if 'favorites' not in session:
        session.permanent = True  # 启用持久会话
        session['favorites'] = []


# 新增路由：收藏夹页面
@app.route('/favorites')
def show_favorites():
    return render_template('favorite.html',
                           favorites=session['favorites'])


@app.route('/add_favorite', methods=['POST'])
def add_favorite():
    video_data = request.json

    # 强制转换数据类型
    video_info = {
        "bvid": str(video_data['bvid']),
        "title": str(video_data['title']),
        "heat": float(video_data['heat'])  # 关键修复：明确转换为 float
    }

    # 检查重复性
    if not any(item['bvid'] == video_info['bvid'] for item in session['favorites']):
        session['favorites'].append(video_info)
        session.modified = True

    return {"status": "success"}

@app.route('/')
def index():
    """主搜索页面"""
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    """处理搜索请求"""
    keywords = request.form.get('keywords', '')
    keyword_list = [k.strip() for k in keywords.split('#') if k.strip()]

    try:
        # 执行搜索
        results = weighted_search(
            query=keyword_list,
            df=df.copy(),
            top_n=5000  # 根据需求调整数量
        )

        # 转换为字典列表并添加序号
        result_data = results.to_dict(orient='records')
        total = len(result_data)

        return render_template(
            'result.html',
            keywords=keywords,
            results=result_data,
            total=total
        )
    except Exception as e:
        return render_template('result.html', error=str(e))


if __name__ == '__main__':
    app.run(debug=True)