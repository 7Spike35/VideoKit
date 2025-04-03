import pandas as pd


def weighted_search(
        query,df,weights={
            'text': 0.6,
            'danmaku': 0.1,
            'like': 0.2,
            'collect': 0.1,
            'view': 0.3
        },
        top_n=100
):
    """
    修正版加权搜索函数
    """
    # ------ 数据预处理 ------
    # 填充缺失值
    df.fillna({
        '弹幕数': 0,
        '点赞数': 0,
        '收藏量': 0,
        '播放量': 0
    }, inplace=True)

    # 标题统一转为小写
    df["标题"] = df["标题"].str.lower()

    # 去重：保留每个bvid的最新记录
    df = df.drop_duplicates('bvid', keep='last')

    # ------ 关键词处理 ------
    # 将关键词列表转换为空格分隔的字符串（适配原函数逻辑）
    query = ' '.join(query).lower()
    keywords = query.split()

    # ------ 文本匹配得分 ------
    df["文本得分"] = df["标题"].apply(
        lambda x: sum(1 for kw in keywords if kw in x) / len(keywords) if keywords else 0
    )

    # ------ 归一化处理 ------
    metrics = ['弹幕数', '点赞数', '收藏量', '播放量']  # 注意列名修正
    for col in metrics:
        df[f"{col}_norm"] = (df[col] - df[col].min()) / (df[col].max() - df[col].min() + 1e-6)

    # ------ 综合得分计算 ------
    df["热度值"] = (
            df["文本得分"] * weights['text'] +
            df["弹幕数_norm"] * weights['danmaku'] +
            df["点赞数_norm"] * weights['like'] +
            df["收藏量_norm"] * weights['collect'] +
            df["播放量_norm"] * weights['view']
    )

    # ------ 结果筛选 ------
    results = (
        df.sort_values("热度值", ascending=False)
        .head(top_n)
        [["标题", "bvid", "热度值", "弹幕数", "点赞数", "收藏量", "播放量"]]  # 添加更多展示字段
    )

    return results


# 使用示例
if __name__ == "__main__":
    query = input("请输入搜索关键词：")
    results = weighted_search(query,".\\file\\bilibili_result.csv")
    print(f"搜索 '{query}' 的结果：")
    print(results.to_string(index=False))