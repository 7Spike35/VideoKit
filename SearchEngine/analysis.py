import pandas as pd
import jieba
from openai import OpenAI
import re
import os
from transformers import BertTokenizer, BertForSequenceClassification
from gensim import corpora, models
import torch

client = OpenAI(
    api_key="sk-MwR5crHOce3aMKVCnxmZBBBxKFbLnLrwJpyNGvvigtL3rvGl",
    base_url="https://api.moonshot.cn/v1",
)


def preprocess_danmu(danmu_list):
    def clean_text(text):
        text = re.sub(r'[^\u4e00-\u9fa5]', '', text)
        return text if len(text) >= 4 else None

    processed = []
    for danmu in danmu_list:
        cleaned = clean_text(danmu)
        if cleaned is not None:
            processed.append(cleaned)
    return processed


def load_pretrained_model():
    model_name = "bert-base-chinese"
    tokenizer = BertTokenizer.from_pretrained(model_name)
    model = BertForSequenceClassification.from_pretrained(model_name).to("cuda:0")
    return model, tokenizer


def topic_modeling(texts, num_topics=5):
    stop_words = \
    pd.read_csv("D:\\PythonProject\\ClassProject\\SearchEngine\\file\\cn_stopwords.txt", encoding='utf-8', header=None)[
        0].tolist()

    def tokenize(text):
        words = jieba.lcut(text)
        return [word for word in words if word not in stop_words]

    tokenized_texts = [tokenize(text) for text in texts]
    dictionary = corpora.Dictionary(tokenized_texts)
    corpus = [dictionary.doc2bow(text) for text in tokenized_texts]

    lda_model = models.LdaModel(corpus, num_topics=num_topics, id2word=dictionary, passes=15)

    topics = []
    for idx, topic in lda_model.print_topics(num_words=5):
        topics.append([word for word, _ in lda_model.show_topic(idx, topn=5)])

    return topics


def generate_summary(topics):
    positive_words = {'好', '喜欢', '开心', '大笑', '优秀', '棒', '赞', '支持',
                      '非常', '不错', '很好', '太棒了', '超喜欢', '欢乐', '兴奋'}
    negative_words = {'差', '讨厌', '无聊', '糟糕', '难过', '生气', '反对',
                      '无语', '失望', '难看', '差评', '很差', '痛苦', '悲伤'}

    summary = "弹幕的总体内容概括：\n"
    for i, topic in enumerate(topics):
        pos_count = sum(1 for word in topic if word in positive_words)
        neg_count = sum(1 for word in topic if word in negative_words)

        sentiment = '积极' if pos_count > neg_count else '消极'
        key_words = ', '.join(topic[:3])

        summary += f"主题{i + 1}：大家对这个话题持有{sentiment}态度，主要讨论内容包括 {key_words}。\n"
    return summary


def chat(query, history):
    history.append({
        "role": "user",
        "content": query
    })
    completion = client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=history,
        temperature=0.3,
    )
    result = completion.choices[0].message.content
    history.append({
        "role": "assistant",
        "content": result
    })
    return result


def sentiment_analysis(model, tokenizer, texts):
    inputs = tokenizer(texts, return_tensors="pt", truncation=True, padding=True, max_length=64)
    inputs = inputs.to("cuda:0")
    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits
    sentiments = torch.argmax(logits, dim=-1).tolist()
    return sentiments


def f(csv_file_path):
    # 验证文件是否存在
    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"评论CSV文件不存在：{csv_file_path}")

    # 读取指定CSV文件
    df = pd.read_csv(csv_file_path)

    # 验证CSV文件是否包含comment列
    if 'comment' not in df.columns:
        raise KeyError("CSV文件中缺少'comment'列")

    # 新增：检查数据是否为空
    if df.empty:  # 修复点：使用df.empty检查空DataFrame
        return {
            'error': '数据文件为空'
        }

    sample_danmu = df['comment'].tolist()

    sentiment_model, sentiment_tokenizer = load_pretrained_model()

    history = [
        {"role": "system",
         "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，准确的回答。同时，你会拒绝一切涉及恐怖主义，种族歧视，黄色暴力等问题的回答。Moonshot AI 为专有名词，不可翻译成其他语言。"}
    ]

    cleaned_data = preprocess_danmu(sample_danmu)

    # 新增：检查清洗后数据是否为空
    if not cleaned_data:  # 修复点：直接检查列表是否为空
        return {
            'error': '有效弹幕数据不足'
        }

    # 情感分析
    sentiment_results = sentiment_analysis(sentiment_model, sentiment_tokenizer, cleaned_data)
    sentiment_df = pd.DataFrame({'danmu': cleaned_data, 'sentiment': sentiment_results})
    sentiment_df['sentiment'] = sentiment_df['sentiment'].replace({0: '消极', 1: '积极'})

    # 计算情感分布
    sentiment_counts = sentiment_df['sentiment'].value_counts().to_dict()
    total_comments = len(sentiment_df)
    sentiment_summary = {
        'positive': sentiment_counts.get('积极', 0) / total_comments * 100 if total_comments > 0 else 0,
        'negative': sentiment_counts.get('消极', 0) / total_comments * 100 if total_comments > 0 else 0
    }

    # 主题分析
    topics = topic_modeling(cleaned_data)

    # 生成摘要
    summary = generate_summary(topics)

    # 生成AI分析
    info = '请你根据我提供的由一系列弹幕进行主题分析生成的主题词，为我分析大家对于该视频有什么看法，主题词如下{topic},请透过现象看本质，生成一段逻辑通顺、语言得体的回答'.format(
        topic=topics)
    ai_analysis = chat(info, history)

    # 返回结构化结果
    return {
        'sentiment': sentiment_summary,
        'keywords': [', '.join(topic) for topic in topics],
        'summary': summary,
        'ai_analysis': ai_analysis,
        'comment_count': len(cleaned_data)
    }


if __name__ == "__main__":
    custom_path = "D:\\pytorchusetrue\\xiaoyangwengproject\\file\\comments.csv"
    result = f(csv_file_path=custom_path)
    print(result)