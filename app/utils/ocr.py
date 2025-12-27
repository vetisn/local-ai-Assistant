# app/utils/ocr.py
"""
轻量级 OCR 文字识别模块
使用 RapidOCR 进行本地文字识别，无需调用视觉模型
"""

from typing import Optional, List, Tuple
from PIL import Image
import io

# 延迟加载 OCR 引擎
_ocr_engine = None


def get_ocr_engine():
    """获取 OCR 引擎（延迟加载）"""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
        except ImportError:
            return None
        except Exception:
            return None
    return _ocr_engine


def ocr_image(image_path: str) -> Optional[str]:
    """
    对图片进行 OCR 文字识别
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        识别出的文字，如果失败返回 None
    """
    engine = get_ocr_engine()
    if engine is None:
        return None
    
    try:
        result, _ = engine(image_path)
        if result:
            # result 格式: [[box, text, confidence], ...]
            texts = [item[1] for item in result]
            return "\n".join(texts)
        return ""
    except Exception:
        return None


def ocr_image_bytes(image_bytes: bytes) -> Optional[str]:
    """
    对图片字节数据进行 OCR 文字识别
    
    Args:
        image_bytes: 图片字节数据
        
    Returns:
        识别出的文字，如果失败返回 None
    """
    engine = get_ocr_engine()
    if engine is None:
        return None
    
    try:
        # 将字节转换为 PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        # RapidOCR 支持 PIL Image 输入
        result, _ = engine(image)
        if result:
            texts = [item[1] for item in result]
            return "\n".join(texts)
        return ""
    except Exception:
        return None


def is_ocr_available() -> bool:
    """检查 OCR 功能是否可用"""
    return get_ocr_engine() is not None
