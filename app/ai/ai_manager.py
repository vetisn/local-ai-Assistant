# app/ai/ai_manager.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Iterable, Generator

import httpx

from app.core.config import settings

# 导入日志记录器
try:
    from app.utils.logger import logger
except ImportError:
    # 如果导入失败，创建一个简单的日志记录器
    import logging
    logger = logging.getLogger(__name__)


class ProviderConfig:
    """
    运行时使用的 Provider 配置。
    既可以从 .env 读全局默认，也可以从 DB Provider 或会话传入。
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ) -> None:
        self.api_base = (api_base or settings.AI_API_BASE or "").rstrip("/")
        self.api_key = (api_key or settings.AI_API_KEY or "").strip()
        self.default_model = default_model or settings.AI_MODEL or "gpt-4o-mini"


class AIManager:
    def __init__(self) -> None:
        # 全局默认 Provider（可被 runtime provider 覆盖）
        try:
            self._provider = ProviderConfig()
        except Exception as e:
            # 静默处理，允许系统启动
            self._provider = ProviderConfig(
                api_base="https://api.openai.com/v1",
                api_key="",
                default_model="gpt-4o-mini"
            )

    def set_provider(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ) -> None:
        """
        从会话 / DB Provider 动态设置当前调用所用的 Provider。
        """
        self._provider = ProviderConfig(
            api_base=api_base,
            api_key=api_key,
            default_model=default_model,
        )

    def is_configured(self) -> bool:
        """检查AI管理器是否已正确配置"""
        return bool(self._provider.api_key and self._provider.api_base)

    async def test_connection(self) -> Dict[str, Any]:
        """测试API连接是否正常"""
        if not self.is_configured():
            return {"success": False, "error": "API Key或API Base未配置"}
        
        try:
            # 发送一个简单的测试请求
            test_messages = [{"role": "user", "content": "test"}]
            result = self.chat(test_messages, stream=False)
            return {"success": True, "message": "连接测试成功"}
        except Exception as e:
            return {"success": False, "error": f"连接测试失败: {str(e)}"}

    # ---------- 内部 HTTP 封装 ----------

    def _headers(self) -> Dict[str, str]:
        if not self._provider.api_key:
            raise ValueError("AI_API_KEY 未配置，请在设置中配置Provider或在.env文件中设置AI_API_KEY")
        return {
            "Authorization": f"Bearer {self._provider.api_key}",
            "Content-Type": "application/json",
        }

    def _post(
        self,
        path: str,
        json_data: Dict[str, Any],
        stream: bool = False,
        timeout: int = 60,
    ) -> httpx.Response:
        url = f"{self._provider.api_base}/{path.lstrip('/')}"
        client_args: Dict[str, Any] = {"timeout": timeout}
        if stream:
            client_args["timeout"] = None  # 流式需要长连接

        client = httpx.Client(**client_args)
        
        try:
            # 使用 build_request + send 来支持 stream=True
            request = client.build_request("POST", url, headers=self._headers(), json=json_data)
            resp = client.send(request, stream=stream)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            client.close()
            raise
        except Exception:
            client.close()
            raise

    # ---------- Chat / Tools ----------

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        stream: bool = False,
        enable_thinking: bool = False,  # 新增：是否启用深度思考
    ) -> Any:
        """
        普通聊天调用。
        - 当 stream=False 时，返回包含内容和token统计的字典。
        - 当 stream=True 时，返回生成器，yield 文本增量。
        - enable_thinking=True 时，启用深度思考模式（需要模型支持）
        """
        payload: Dict[str, Any] = {
            "model": model or self._provider.default_model,
            "messages": messages,
            "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        
        # 深度思考模式配置
        # 注意：不同的 API 提供商可能有不同的参数格式
        if enable_thinking:
            model_name = (model or self._provider.default_model or "").lower()
            
            # Gemini 模型使用 Google 的格式
            if "gemini" in model_name:
                # Google Gemini 通过 OpenAI 兼容 API 的思考模式
                # 参考: https://ai.google.dev/gemini-api/docs/openai
                payload["reasoning_effort"] = "medium"
                # 注意：某些中转 API 可能不支持 thinking 参数，先注释掉
                # payload["thinking"] = {"type": "enabled", "budget_tokens": 10000}
            elif "deepseek" in model_name or "r1" in model_name:
                # DeepSeek R1 模型
                payload["reasoning_effort"] = "medium"
            elif "o1" in model_name or "o3" in model_name:
                # OpenAI o1/o3 模型
                payload["reasoning_effort"] = "medium"
            else:
                # 其他模型尝试通用格式
                payload["reasoning_effort"] = "medium"
        
        # 记录详细的API调用信息

        try:
            logger.log_ai_api_call(
                api_base=self._provider.api_base,
                model=payload["model"],
                messages_count=len(messages),
                stream=stream
            )
            
            # 记录消息内容（用于调试token使用）
            total_chars = sum(len(msg.get('content') or '') for msg in messages)
            logger.log_performance("消息准备", 0, {
                "messages_count": len(messages),
                "total_characters": total_chars,
                "average_chars_per_message": total_chars / len(messages) if messages else 0
            })
            
        except Exception:
            pass
        
        if not stream:
            resp = self._post("chat/completions", payload, stream=False)
            try:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                
                result = {
                    "content": content,
                    "model": payload["model"],
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                }
                
                # 记录token使用情况
                try:
                    logger.log_token_usage(
                        model=result["model"],
                        input_tokens=result["input_tokens"],
                        output_tokens=result["output_tokens"],
                        total_tokens=result["total_tokens"]
                    )
                except Exception:
                    pass
                
                return result
            finally:
                resp.close()

        # 流式：返回一个生成器
        resp = self._post("chat/completions", payload, stream=True)

        def _iter() -> Generator[Dict[str, Any], None, None]:
            usage_info = None
            try:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        # 在结束前 yield 最后收集到的 usage 信息
                        if usage_info:
                            yield {"type": "usage", "usage": usage_info}
                        break
                    try:
                        import json as _json
                        obj = _json.loads(line)
                    except Exception:
                        continue

                    # usage 信息（持续更新，在流结束时 yield）
                    usage = obj.get("usage")
                    if usage and usage.get("prompt_tokens"):
                        usage_info = {
                            "model": payload["model"],
                            "input_tokens": usage.get("prompt_tokens", 0),
                            "output_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                        }

                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    
                    # 检查是否有思考内容（深度思考模式）
                    # 支持多种格式：reasoning_content, thinking, 或 <thought> 标签
                    reasoning = delta.get("reasoning_content") or delta.get("thinking") or ""
                    content = delta.get("content") or ""
                    
                    # 如果 content 为空但 reasoning 有内容，需要判断这是真正的思考还是最终回复
                    # DeepSeek 模型有时会把最终回复也放在 reasoning_content 中
                    if reasoning and not content:
                        # 先作为思考内容输出
                        yield {"type": "thinking", "content": reasoning}
                    elif reasoning and content:
                        # 两者都有，分别输出
                        yield {"type": "thinking", "content": reasoning}
                    
                    # Gemini 的思考内容可能包裹在 <thought> 标签中
                    if content:
                        # 检查是否包含 <thought> 标签
                        if "<thought>" in content or "</thought>" in content:
                            # 提取思考内容
                            import re
                            thought_match = re.search(r'<thought>(.*?)</thought>', content, re.DOTALL)
                            if thought_match:
                                thinking_text = thought_match.group(1)
                                yield {"type": "thinking", "content": thinking_text}
                                # 移除思考内容，保留正文
                                content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL)
                            elif "<thought>" in content and "</thought>" not in content:
                                # 思考开始但未结束，整个内容都是思考
                                thinking_text = content.replace("<thought>", "")
                                yield {"type": "thinking", "content": thinking_text}
                                content = ""
                            elif "</thought>" in content and "<thought>" not in content:
                                # 思考结束
                                thinking_text = content.replace("</thought>", "")
                                yield {"type": "thinking", "content": thinking_text}
                                content = ""
                    
                    if content:
                        yield {"type": "content", "content": content}
            finally:
                resp.close()

        return _iter()


    def run_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        stream: bool = False,
    ) -> Any:
        """
        支持 tools 的对话调用。
        - tools 为 None 时相当于普通 chat。
        - stream 语义同 chat()。
        """
        payload: Dict[str, Any] = {
            "model": model or self._provider.default_model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        if stream:
            payload["stream_options"] = {"include_usage": True}

        if not stream:
            # 工具调用模式需要更长的超时时间（120秒）
            resp = self._post("chat/completions", payload, stream=False, timeout=120)
            try:
                data = resp.json()
                # 格式化返回数据，确保包含token信息
                if "usage" in data:
                    usage = data["usage"]
                    data["token_info"] = {
                        "model": payload["model"],
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0)
                    }
                return data
            finally:
                resp.close()

        resp = self._post("chat/completions", payload, stream=True)

        def _iter() -> Generator[Dict[str, Any], None, None]:
            try:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    # 修复：iter_lines() 返回 str
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        break
                    try:
                        obj = httpx.Response(200, content=line).json()
                    except Exception:
                        continue
                    yield obj
            finally:
                resp.close()

        return _iter()

    # ---------- Embedding（向量生成） ----------

    def create_embedding(
        self,
        input_texts: Iterable[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """
        为知识库构建向量，调用 OpenAI 兼容的 /embeddings 接口。
        返回：每个输入文本对应的向量列表。
        """
        texts = list(input_texts)
        if not texts:
            return []

        # 使用指定的向量模型，如果没有指定则使用默认的
        embedding_model = model or settings.EMBEDDING_MODEL
        payload: Dict[str, Any] = {
            "model": embedding_model,
            "input": texts,
        }
        url_path = "embeddings"

        url = f"{self._provider.api_base}/{url_path}"
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()

        embeddings: List[List[float]] = []
        for item in data.get("data", []):
            emb = item.get("embedding")
            if isinstance(emb, list):
                embeddings.append(emb)
        return embeddings

    # ---------- Image Generation（图像生成） ----------

    def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: str = "1024x1024",
        n: int = 1,
        response_format: str = "url",  # "url" 或 "b64_json"
    ) -> Dict[str, Any]:
        """
        调用图像生成 API（兼容 OpenAI DALL-E 格式）。
        
        参数：
        - prompt: 图像描述
        - model: 生图模型名称
        - size: 图像尺寸，如 "1024x1024", "1792x1024", "1024x1792"
        - n: 生成图片数量
        - response_format: 返回格式，"url" 或 "b64_json"
        
        返回：
        {
            "success": True/False,
            "images": [{"url": "..."} 或 {"b64_json": "..."}],
            "error": "错误信息（如果失败）"
        }
        """
        if not model:
            return {"success": False, "error": "未指定生图模型", "images": []}
        
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": n,
            "response_format": response_format,
        }
        
        try:
            logger.info(
                "图像生成请求",
                model=model,
                prompt_length=len(prompt),
                size=size,
                n=n
            )
            
            url = f"{self._provider.api_base}/images/generations"
            with httpx.Client(timeout=120) as client:  # 生图可能需要更长时间
                resp = client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
            
            images = data.get("data", [])
            
            logger.info(
                "图像生成成功",
                model=model,
                images_count=len(images)
            )
            
            return {
                "success": True,
                "images": images,
                "model": model
            }
            
        except httpx.HTTPStatusError as e:
            error_msg = f"API 错误: {e.response.status_code}"
            try:
                error_data = e.response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except:
                pass
            logger.error("图像生成失败", error=error_msg)
            return {"success": False, "error": error_msg, "images": []}
            
        except Exception as e:
            logger.error("图像生成异常", error=str(e))
            return {"success": False, "error": str(e), "images": []}
