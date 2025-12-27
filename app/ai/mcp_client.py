# app/ai/mcp_client.py
"""
MCP (Model Context Protocol) 客户端
支持通过 stdio 与 MCP 服务器通信
"""
import asyncio
import json
import subprocess
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPServer:
    """MCP 服务器配置"""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    process: Optional[subprocess.Popen] = None
    tools: List[MCPTool] = field(default_factory=list)
    _request_id: int = 0


class MCPClient:
    """MCP 客户端管理器"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._tool_name_map: Dict[str, tuple] = {}  # 工具名称映射：清理后名称 -> (原始服务器名, 原始工具名)
    
    def add_server(self, name: str, command: str, args: List[str] = None, env: Dict[str, str] = None):
        """添加 MCP 服务器配置"""
        self.servers[name] = MCPServer(
            name=name,
            command=command,
            args=args or [],
            env=env or {}
        )
        self._locks[name] = asyncio.Lock()
    
    async def start_server(self, name: str) -> bool:
        """启动指定的 MCP 服务器"""
        if name not in self.servers:
            print(f"[MCP] 服务器 {name} 未配置")
            return False
        
        server = self.servers[name]
        if server.process and server.process.poll() is None:
            print(f"[MCP] 服务器 {name} 已在运行")
            return True
        
        try:
            cmd = [server.command] + server.args
            print(f"[MCP] 启动服务器: {' '.join(cmd)}")
            
            # 合并环境变量
            env = dict(os.environ)
            env.update(server.env)
            
            server.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=0
            )
            
            # 初始化连接
            await self._initialize_server(server)
            
            # 获取工具列表
            await self._list_tools(server)
            
            print(f"[MCP] 服务器 {name} 启动成功，可用工具: {[t.name for t in server.tools]}")
            return True
            
        except Exception as e:
            print(f"[MCP] 启动服务器 {name} 失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _send_request(self, server: MCPServer, method: str, params: Dict = None) -> Dict:
        """发送 JSON-RPC 请求"""
        lock = self._locks.get(server.name)
        if not lock:
            lock = asyncio.Lock()
            self._locks[server.name] = lock
            
        async with lock:
            server._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": server._request_id,
                "method": method,
            }
            if params:
                request["params"] = params
            
            request_str = json.dumps(request) + "\n"
            print(f"[MCP] 发送请求: {request_str.strip()}")
            
            server.process.stdin.write(request_str.encode())
            server.process.stdin.flush()
            
            # 读取响应
            response_line = await asyncio.get_event_loop().run_in_executor(
                None, server.process.stdout.readline
            )
            
            if not response_line:
                raise Exception("服务器无响应")
            
            response = json.loads(response_line.decode())
            print(f"[MCP] 收到响应: {json.dumps(response, ensure_ascii=False)[:500]}")
            
            if "error" in response:
                raise Exception(f"MCP 错误: {response['error']}")
            
            return response.get("result", {})
    
    async def _initialize_server(self, server: MCPServer):
        """初始化 MCP 服务器连接"""
        result = await self._send_request(server, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "ai-chat-client",
                "version": "1.0.0"
            }
        })
        
        # 发送 initialized 通知
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        server.process.stdin.write((json.dumps(notification) + "\n").encode())
        server.process.stdin.flush()
        
        return result
    
    async def _list_tools(self, server: MCPServer):
        """获取服务器的工具列表"""
        result = await self._send_request(server, "tools/list", {})
        
        server.tools = []
        for tool in result.get("tools", []):
            server.tools.append(MCPTool(
                name=tool["name"],
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {})
            ))
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict = None) -> Dict:
        """调用 MCP 工具"""
        if server_name not in self.servers:
            return {"error": f"服务器 {server_name} 未配置"}
        
        server = self.servers[server_name]
        if not server.process or server.process.poll() is not None:
            # 尝试重新启动
            if not await self.start_server(server_name):
                return {"error": f"服务器 {server_name} 未运行且无法启动"}
        
        try:
            result = await self._send_request(server, "tools/call", {
                "name": tool_name,
                "arguments": arguments or {}
            })
            return {"success": True, "result": result}
        except Exception as e:
            return {"error": str(e)}
    
    def _sanitize_tool_name(self, name: str) -> str:
        """
        清理工具名称，确保符合 API 要求：
        - 只允许 a-z, A-Z, 0-9, 下划线(_), 点(.), 冒号(:), 短横线(-)
        - 必须以字母或下划线开头
        """
        import re
        # 将非 ASCII 字符和不允许的字符替换为下划线
        sanitized = re.sub(r'[^a-zA-Z0-9_.\-:]', '_', name)
        # 确保以字母或下划线开头
        if sanitized and not re.match(r'^[a-zA-Z_]', sanitized):
            sanitized = '_' + sanitized
        # 合并连续的下划线
        sanitized = re.sub(r'_+', '_', sanitized)
        # 移除末尾的下划线
        sanitized = sanitized.rstrip('_')
        return sanitized or 'unnamed'

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有服务器的工具列表（OpenAI tools 格式）"""
        tools = []
        # 清空并重建工具名称映射
        self._tool_name_map = {}
        
        for server_name, server in self.servers.items():
            # 清理服务器名称，移除中文等非法字符
            safe_server_name = self._sanitize_tool_name(server_name)
            for tool in server.tools:
                safe_tool_name = self._sanitize_tool_name(tool.name)
                full_tool_name = f"mcp_{safe_server_name}_{safe_tool_name}"
                
                # 保存映射：清理后的完整工具名 -> (原始服务器名, 原始工具名)
                self._tool_name_map[full_tool_name] = (server_name, tool.name)
                
                tools.append({
                    "type": "function",
                    "function": {
                        "name": full_tool_name,
                        "description": f"[MCP:{server_name}] {tool.description}",
                        "parameters": tool.input_schema
                    }
                })
        return tools
    
    def parse_tool_name(self, full_tool_name: str) -> tuple:
        """
        解析工具名称，返回 (服务器名, 工具名)
        如果找不到映射，尝试使用旧的解析方式作为后备
        """
        # 首先尝试从映射中查找
        if hasattr(self, '_tool_name_map') and full_tool_name in self._tool_name_map:
            return self._tool_name_map[full_tool_name]
        
        # 后备方案：使用旧的解析方式（兼容没有中文的情况）
        if full_tool_name.startswith("mcp_"):
            parts = full_tool_name.split("_", 2)
            if len(parts) >= 3:
                return (parts[1], parts[2])
        
        return (None, None)
    
    def get_tools_for_display(self) -> List[Dict[str, Any]]:
        """获取工具列表用于前端显示"""
        tools = []
        for server_name, server in self.servers.items():
            for tool in server.tools:
                tools.append({
                    "server": server_name,
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.input_schema
                })
        return tools
    
    async def stop_server(self, name: str):
        """停止指定的 MCP 服务器"""
        if name in self.servers:
            server = self.servers[name]
            if server.process:
                server.process.terminate()
                try:
                    server.process.wait(timeout=5)
                except:
                    server.process.kill()
                server.process = None
                print(f"[MCP] 服务器 {name} 已停止")
    
    async def stop_all(self):
        """停止所有 MCP 服务器"""
        for name in list(self.servers.keys()):
            await self.stop_server(name)


# 全局 MCP 客户端实例
mcp_client = MCPClient()
