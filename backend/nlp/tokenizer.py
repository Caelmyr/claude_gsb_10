"""
中文分词模块 - 使用jieba分词
"""
import jieba
import jieba.posseg as pseg


class ChineseTokenizer:
    """中文分词器"""

    def __init__(self):
        # 加载自定义词典（可选）
        pass

    def tokenize(self, text: str) -> list:
        """分词并返回词语列表"""
        return list(jieba.cut(text))

    def tokenize_with_pos(self, text: str) -> list:
        """分词并返回(词, 词性)列表"""
        return [(word, flag) for word, flag in pseg.cut(text)]

    def segment_sentences(self, text: str) -> list:
        """将文本分割为句子"""
        import re
        sentences = re.split(r'[。！？；\n]+', text)
        return [s.strip() for s in sentences if s.strip()]
