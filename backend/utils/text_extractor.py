"""
文档文本提取模块 - 支持TXT和PDF格式
"""
import os
import pdfplumber


def extract_text(file_path: str) -> str:
    """从文件中提取文本内容"""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.txt':
        return _extract_from_txt(file_path)
    elif ext == '.pdf':
        return _extract_from_pdf(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def _extract_from_txt(file_path: str) -> str:
    """从TXT文件提取文本"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"无法解码文件: {file_path}")


def _extract_from_pdf(file_path: str) -> str:
    """从PDF文件提取文本"""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return '\n'.join(text_parts)
