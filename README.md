# 本地 AI 助手

一个轻量级的本地 AI 助手 Web 界面，支持多模型、知识库、MCP 工具、联网搜索等功能。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特性

- **多 Provider 支持** - 兼容 OpenAI API 格式，可配置多个模型提供商
- **模型能力标记** - 视觉识别、深度推理、对话、图像生成
- **知识库 (RAG)** - 文档上传、向量检索、智能问答
- **MCP 工具调用** - 支持 Model Context Protocol 工具集成
- **联网搜索** - DuckDuckGo（免费）/ Tavily 搜索引擎
- **图像生成** - 支持 DALL-E 等生图模型
- **流式输出** - 实时渲染，Token 统计
- **Markdown 渲染** - 代码高亮、数学公式、表格等

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python start.py
```

### 3. 访问界面

打开浏览器访问 http://localhost:8000

### 4. 配置 Provider

点击「设置」→「管理 Provider」，添加你的 AI 服务：

| 字段 | 说明 | 示例 |
|------|------|------|
| API Base URL | API 服务地址 | `https://api.openai.com/v1` |
| API Key | 密钥（可选） | `sk-xxx` |
| 模型列表 | 添加可用模型 | `gpt-4o`, `gpt-4o-mini` |

为每个模型勾选其支持的能力：👁 视觉 | 🧠 推理 | 💬 对话 | 🎨 生图

## 📖 功能说明

### 知识库

1. 「设置」→「管理知识库」→ 创建知识库
2. 选择向量模型，上传文档
3. 对话时开启「📚」开关

**支持格式**：PDF, Word, PPT, Excel, TXT, Markdown, CSV, JSON, XML, HTML, 图片

### MCP 工具

1. 「设置」→「管理 MCP」→ 添加服务器
2. 支持 STDIO（本地）和 HTTP（远程）两种方式
3. 对话时开启「🔧」开关

### 联网搜索

1. 「设置」→「配置联网搜索」
2. 选择搜索源（DuckDuckGo 免费，Tavily 需 API Key）
3. 对话时开启「🌐」开关

### 图像生成

1. 配置生图模型（如 dall-e-3），勾选「生图」能力
2. 点击「🎨」按钮，选择模型和尺寸
3. 输入描述即可生成

## 📁 项目结构

```
├── app/                    # 后端代码
│   ├── ai/                 # AI 模块
│   ├── core/               # 核心配置
│   ├── db/                 # 数据库
│   └── utils/              # 工具函数
├── frontend/               # 前端代码
├── logs/                   # 日志目录
├── uploads/                # 上传文件
├── start.py                # 启动脚本
└── requirements.txt        # 依赖列表
```

## 🔧 常见问题

**Q: 端口被占用？**
修改 `start.py` 中的端口号。

**Q: API 调用失败？**
检查 Provider 配置，确保 API Base URL 和 API Key 正确。

**Q: 如何重置数据？**
```bash
del app.db          # Windows
rm app.db           # Linux/Mac
python start.py     # 重启自动创建
```

**Q: 如何导出日志？**
「设置」→「导出日志」，或运行 `python collect_logs.py`

## 🛠️ 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite
- **前端**：原生 JavaScript + Marked.js + Highlight.js + KaTeX
- **HTTP**：httpx + requests

## 📄 许可证

MIT License

## 📮 联系方式

- GitHub Issues: [提交问题](https://github.com/vetisn/local-ai-Assistant/issues)
- 邮箱: 2414644363@qq.com

---

> 本项目大部分代码由 AI 辅助完成，仅供学习研究使用。
