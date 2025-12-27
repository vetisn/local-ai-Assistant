# app/ai/tools.py
import json
import textwrap
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db import crud
from app.db.database import SessionLocal
from app.core.config import settings

# 已有：本地工具定义 -------------------------------------------------

def get_local_time_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "get_local_time",
            "description": "获取当前服务器的本地时间。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }

def run_get_local_time_tool() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_calculator_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "calculate_expression",
            "description": "计算一个简单的数学表达式，例如 1+2*3。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "需要计算的数学表达式，例如 '1+2*3'",
                    }
                },
                "required": ["expression"],
            },
        },
    }

def run_calculator_tool(expression: str) -> str:
    # 简单 eval，仅示例，生产环境要加沙盒
    try:
        value = eval(expression, {"__builtins__": {}})
    except Exception as e:
        return f"表达式计算错误: {e}"
    return str(value)

# === 新增：知识库检索工具定义 ====================================

def search_knowledge_tool_schema() -> Dict[str, Any]:
    """
    OpenAI tools schema: 知识库检索工具定义。
    """
    return {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "在本地知识库中检索相关内容。当用户问题涉及知识库中的专业知识时请积极使用。建议：使用精准的关键词搜索，避免过于宽泛的查询，尽量一次搜索获取足够信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，应该具体且相关。例如：'蠕变的三个阶段' 比 '蠕变' 更精准。",
                    },
                    "kb_id": {
                        "type": "integer",
                        "description": "可选，指定要检索的知识库 ID，不填则搜索所有知识库。",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认5条，通常足够。",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    }

def run_search_knowledge_tool(
    *,
    query: str,
    kb_id: Optional[int] = None,
    top_k: int = 5,
    embedding_fn=None,
    use_graph: bool = True,  # 新增：是否使用知识图谱增强
) -> str:
    """
    知识库检索工具的实际执行逻辑：

    1. 使用 embedding_fn(query) 生成 query 向量；
    2. 用 crud.search_knowledge_chunks 在 DB 中做向量相似度检索；
    3. （可选）从知识图谱中获取相关实体和关系；
    4. 把检索到的内容拼成一段说明文字返回给大模型。

    embedding_fn: 一个函数，签名类似：
        embedding_fn([text: str]) -> List[List[float]]
    由调用方传入（通常是 AIManager.create_embedding）。
    """
    
    parts: List[str] = []
    db: Session = SessionLocal()
    
    try:
        # 1. 知识图谱检索（如果启用）
        if use_graph:
            try:
                from app.ai.knowledge_graph import search_graph_context
                graph_context = search_graph_context(db, query, kb_id=kb_id, max_entities=3)
                if graph_context:
                    parts.append(graph_context)
            except Exception:
                pass  # 知识图谱检索失败时静默处理
        
        # 2. 向量检索
        if embedding_fn is not None:
            try:
                embeddings = embedding_fn([query])
                
                if embeddings:
                    query_embedding = embeddings[0]
                    
                    chunks = crud.search_knowledge_chunks(
                        db,
                        query_embedding=query_embedding,
                        kb_id=kb_id,
                        top_k=top_k,
                    )
                    
                    if chunks:
                        parts.append("\n【向量检索结果】")
                        for idx, chunk in enumerate(chunks, start=1):
                            doc = chunk.document
                            kb_name = doc.kb.name if doc and doc.kb else settings.KNOWLEDGE_DEFAULT_KB_NAME
                            parts.append(
                                textwrap.dedent(
                                    f"""
                                    [片段 {idx} | 知识库: {kb_name} | 文档: {doc.file_name if doc else '未知'}]
                                    {chunk.content}
                                    """
                                ).strip()
                            )
            except Exception:
                pass  # 向量检索失败时静默处理
    finally:
        db.close()

    if not parts:
        return "知识库中没有找到与当前问题足够相关的内容。"

    result = "\n\n".join(parts)
    return result

# === 新增：联网搜索工具定义 ====================================

def web_search_tool_schema() -> Dict[str, Any]:
    """
    OpenAI tools schema: 联网搜索工具定义。
    """
    return {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "在互联网上搜索最新信息，获取实时数据和最新资讯。建议使用精准的搜索关键词。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题，用于在互联网上查找相关信息。",
                    },
                },
                "required": ["query"],
            },
        },
    }

def _search_with_duckduckgo(query: str) -> str:
    """
    使用 DuckDuckGo 搜索（免费，无需 API Key）
    """
    import requests
    import json
    
    try:
        # 首先尝试 DuckDuckGo HTML 搜索（更可靠）
        result = _search_duckduckgo_html(query)
        if result and "未找到相关结果" not in result and "搜索失败" not in result:
            return result
        
        # DuckDuckGo Instant Answer API 作为备选
        url = "https://api.duckduckgo.com/"
        params = {
            'q': query,
            'format': 'json',
            'no_html': 1,
            'skip_disambig': 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            results = []
            
            # 获取摘要答案
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", "摘要"),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("Abstract", "")
                })
            
            # 获取相关主题
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:50] + "...",
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", "")
                    })
            
            if results:
                return json.dumps({
                    "query": query,
                    "source": "duckduckgo",
                    "results": results[:3]
                }, ensure_ascii=False, indent=2)
            else:
                return json.dumps({
                    "query": query,
                    "source": "duckduckgo",
                    "results": [],
                    "message": "未找到相关结果，请尝试更换关键词"
                }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "query": query,
                "source": "duckduckgo",
                "results": [],
                "error": f"搜索请求失败，状态码: {response.status_code}"
            }, ensure_ascii=False, indent=2)
            
    except Exception as e:
        return json.dumps({
            "query": query,
            "source": "duckduckgo",
            "results": [],
            "error": f"搜索失败: {str(e)}"
        }, ensure_ascii=False, indent=2)

def _search_duckduckgo_html(query: str) -> str:
    """
    DuckDuckGo HTML 搜索备选方案
    """
    import requests
    import json
    import re
    from html import unescape
    
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        data = {'q': query, 'b': ''}
        
        response = requests.post(url, headers=headers, data=data, timeout=15)
        
        if response.status_code == 200:
            html = response.text
            results = []
            
            # 方法1: 匹配 result__a 链接（主要方法）
            # 格式: <a rel="nofollow" class="result__a" href="...">标题</a>
            pattern1 = r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
            matches1 = re.findall(pattern1, html, re.IGNORECASE | re.DOTALL)
            
            # 方法2: 匹配 result__snippet 摘要
            snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>([^<]*(?:<[^>]*>[^<]*)*)</a>'
            snippets_raw = re.findall(snippet_pattern, html, re.IGNORECASE | re.DOTALL)
            # 清理HTML标签
            snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets_raw]
            
            # 方法3: 如果方法1失败，尝试匹配整个 result 块
            if not matches1:
                # 匹配整个结果块
                result_blocks = re.findall(r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.IGNORECASE | re.DOTALL)
                
                for block in result_blocks[:5]:
                    # 从块中提取链接和标题
                    link_match = re.search(r'href="([^"]+)"[^>]*>([^<]+)</a>', block)
                    if link_match:
                        url_found = link_match.group(1)
                        title = unescape(link_match.group(2).strip())
                        # 提取摘要
                        snippet_match = re.search(r'class="result__snippet"[^>]*>([^<]+)', block)
                        snippet = unescape(snippet_match.group(1).strip()) if snippet_match else ""
                        
                        if url_found and title and not url_found.startswith('/'):
                            results.append({
                                "title": title[:100],
                                "url": url_found,
                                "snippet": snippet[:200]
                            })
            else:
                # 使用方法1的结果
                for i, (url_found, title) in enumerate(matches1[:5]):
                    # 解码URL（DuckDuckGo会编码URL）
                    if 'uddg=' in url_found:
                        # 提取真实URL
                        real_url_match = re.search(r'uddg=([^&]+)', url_found)
                        if real_url_match:
                            from urllib.parse import unquote
                            url_found = unquote(real_url_match.group(1))
                    
                    title = unescape(title.strip())
                    snippet = unescape(snippets[i].strip()) if i < len(snippets) else ""
                    
                    if url_found and title:
                        results.append({
                            "title": title[:100],
                            "url": url_found,
                            "snippet": snippet[:200]
                        })
            
            if results:
                return json.dumps({
                    "query": query,
                    "source": "duckduckgo",
                    "results": results[:3]
                }, ensure_ascii=False, indent=2)
            else:
                # 保存部分HTML用于调试
                return json.dumps({
                    "query": query,
                    "source": "duckduckgo",
                    "results": [],
                    "message": "未找到相关结果"
                }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "query": query,
                "source": "duckduckgo",
                "results": [],
                "error": f"搜索请求失败，状态码: {response.status_code}"
            }, ensure_ascii=False, indent=2)
            
    except Exception as e:
        return json.dumps({
            "query": query,
            "source": "duckduckgo",
            "results": [],
            "error": f"搜索失败: {str(e)}"
        }, ensure_ascii=False, indent=2)

def _search_with_tavily(query: str) -> str:
    """
    使用 Tavily 搜索（需要 API Key）
    """
    import requests
    import json
    
    try:
        # 从数据库获取 API Key
        tavily_api_key = None
        try:
            db = SessionLocal()
            setting = crud.get_setting(db, "tavily_api_key")
            tavily_api_key = setting.value if setting else None
            db.close()
        except Exception:
            pass  # 获取 API Key 失败时静默处理
        
        if not tavily_api_key:
            return _search_with_duckduckgo(query)
        
        # Tavily API 调用
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "include_images": False,
            "include_raw_content": False,
            "max_results": 5
        }
        response = requests.post(url, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                return json.dumps({
                    "query": query,
                    "source": "tavily",
                    "results": [],
                    "message": "未找到相关结果"
                }, ensure_ascii=False, indent=2)
            
            formatted_results = []
            for result in results[:3]:
                formatted_results.append({
                    "title": result.get("title", "无标题"),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", "无内容")[:200]
                })
            
            return json.dumps({
                "query": query,
                "source": "tavily",
                "results": formatted_results
            }, ensure_ascii=False, indent=2)
        elif response.status_code == 401:
            return _search_with_duckduckgo(query)
        else:
            return json.dumps({
                "query": query,
                "source": "tavily",
                "results": [],
                "error": f"搜索请求失败，状态码: {response.status_code}"
            }, ensure_ascii=False, indent=2)
            
    except Exception as e:
        return json.dumps({
            "query": query,
            "source": "tavily",
            "results": [],
            "error": f"搜索失败: {str(e)}"
        }, ensure_ascii=False, indent=2)

def run_web_search_tool(
    *,
    query: str,
    source: str = None,
    db_session=None,
) -> str:
    """
    联网搜索工具的实际执行逻辑
    source 参数现在从数据库设置中读取默认值
    """
    # 如果没有指定 source，从数据库读取默认设置
    if not source:
        try:
            db = SessionLocal()
            setting = crud.get_setting(db, "default_search_source")
            source = setting.value if setting else "duckduckgo"
            db.close()
        except Exception:
            source = "duckduckgo"
    
    try:
        if source == "tavily":
            return _search_with_tavily(query)
        else:
            return _search_with_duckduckgo(query)
    except Exception as e:
        return f"搜索失败: {str(e)}"

# 统一对外接口：根据开关组合返回工具列表 -----------------------------

def get_tools(
    *,
    enable_knowledge_base: bool = False,
    enable_mcp: bool = False,
    enable_web_search: bool = False,
    mcp_tools: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    根据功能开关返回需要注册给 OpenAI 的 tools 列表。

    - enable_knowledge_base: 是否启用知识库检索工具 search_knowledge
    - enable_mcp: MCP 相关工具预留（暂未实现）
    - enable_web_search: 是否启用联网搜索工具 web_search
    - mcp_tools: MCP 工具列表（已转换为 OpenAI 格式）
    """
    tools: List[Dict[str, Any]] = []

    # 知识库工具
    if enable_knowledge_base:
        tools.append(search_knowledge_tool_schema())

    # 联网搜索工具
    if enable_web_search:
        tools.append(web_search_tool_schema())

    # MCP 工具
    if enable_mcp and mcp_tools:
        tools.extend(mcp_tools)

    return tools
