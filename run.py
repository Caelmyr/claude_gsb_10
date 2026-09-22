#!/usr/bin/env python3
"""
知识图谱问答系统 - 一键启动脚本
"""
import sys
import os
import webbrowser
import threading
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import app
from backend.utils.config import API_HOST, API_PORT


def open_browser():
    """延迟打开浏览器"""
    time.sleep(1.5)
    webbrowser.open(f'http://localhost:{API_PORT}')


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("   📚 知识图谱构建与智能问答系统")
    print("=" * 60)

    print("\n🚀 系统启动中...\n")

    print("📍 前端访问地址:")
    print("   ┌─────────────────────────────────────────────────┐")
    print(f"   │  🏠 首页(文档管理): http://localhost:{API_PORT}              │")
    print(f"   │  🏷️ 实体标注:      http://localhost:{API_PORT}/annotate.html │")
    print(f"   │  🕸️ 知识图谱:      http://localhost:{API_PORT}/graph.html    │")
    print(f"   │  💬 智能问答:      http://localhost:{API_PORT}/chat.html     │")
    print(f"   │  📊 统计面板:      http://localhost:{API_PORT}/stats.html    │")
    print("   └─────────────────────────────────────────────────┘")

    print("\n📡 后端API地址:")
    print(f"   http://localhost:{API_PORT}/api/")

    print("\n" + "-" * 60)
    print("💡 使用说明:")
    print("   1. 上传TXT/PDF文档")
    print("   2. 解析文档提取实体关系")
    print("   3. 查看知识图谱可视化")
    print("   4. 进行智能问答对话")
    print("-" * 60)

    print("\n⚠️  按 Ctrl+C 停止服务器\n")

    # 自动打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动Flask服务器
    app.run(host=API_HOST, port=API_PORT, debug=False)
