#!/usr/bin/env python3
"""
依赖检查脚本
检查当前环境中已安装的依赖包
"""

import sys
import importlib
import subprocess

# 核心依赖
CORE_DEPS = [
    ("fastapi", "FastAPI Web框架"),
    ("uvicorn", "ASGI服务器"),
    ("sqlmodel", "数据库ORM"),
    ("pydantic", "数据验证"),
    ("httpx", "HTTP客户端"),
    ("requests", "HTTP请求库"),
    ("openai", "OpenAI SDK"),
    ("python_dotenv", "环境变量管理"),
]

# 可选依赖
OPTIONAL_DEPS = [
    ("PyPDF2", "PDF文件处理"),
    ("docx", "Word文档处理"),
    ("PIL", "图像处理"),
    ("pytesseract", "OCR识别"),
    ("markdown", "Markdown处理"),
    ("chromadb", "向量数据库"),
    ("sentence_transformers", "本地向量模型"),
    ("numpy", "数值计算"),
    ("pandas", "数据分析"),
    ("jieba", "中文分词"),
]

def check_package(package_name, description):
    """检查单个包是否已安装"""
    try:
        importlib.import_module(package_name)
        return True, "✅"
    except ImportError:
        return False, "❌"

def get_package_version(package_name):
    """获取包版本"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True,
            text=True,
            check=True
        )
        for line in result.stdout.split('\n'):
            if line.startswith('Version:'):
                return line.split(':', 1)[1].strip()
    except:
        pass
    return "未知"

def main():
    """主检查流程"""
    print("🔍 依赖包检查报告")
    print("=" * 60)
    
    print("\n📦 核心依赖 (必需)")
    print("-" * 40)
    core_missing = []
    for package, desc in CORE_DEPS:
        installed, status = check_package(package, desc)
        version = get_package_version(package) if installed else ""
        version_str = f" ({version})" if version and version != "未知" else ""
        print(f"{status} {package:<20} {desc}{version_str}")
        if not installed:
            core_missing.append(package)
    
    print("\n🔧 可选依赖 (增强功能)")
    print("-" * 40)
    optional_available = []
    for package, desc in OPTIONAL_DEPS:
        installed, status = check_package(package, desc)
        version = get_package_version(package) if installed else ""
        version_str = f" ({version})" if version and version != "未知" else ""
        print(f"{status} {package:<20} {desc}{version_str}")
        if installed:
            optional_available.append(package)
    
    print("\n📊 总结")
    print("-" * 40)
    if core_missing:
        print(f"❌ 缺少 {len(core_missing)} 个核心依赖: {', '.join(core_missing)}")
        print("💡 请运行: pip install -r requirements.txt")
    else:
        print("✅ 所有核心依赖已安装")
    
    if optional_available:
        print(f"✅ 已安装 {len(optional_available)} 个可选依赖")
    else:
        print("ℹ️  未安装可选依赖")
        print("💡 如需完整功能，请运行: pip install -r requirements.txt")
    
    print("\n🚀 启动建议")
    print("-" * 40)
    if not core_missing:
        print("✅ 可以启动应用: python start.py")
    else:
        print("❌ 请先安装缺少的依赖")
    
    return len(core_missing) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)