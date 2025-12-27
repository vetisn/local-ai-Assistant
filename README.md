<div align="center">

# 🔮 灵枢 · Linga Chat

**一个功能丰富的本地 AI 助手 Web 界面**

支持多模型、智能视觉识别、知识库 RAG、MCP 工具调用、联网搜索、图像生成等功能

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

</div>

---

## ✨ 核心特性

### 🤖 多 Provider 多模型支持
- **多 Provider 管理** - 同时配置 OpenAI、智谱、DeepSeek、Gemini 等多个服务商
- **模型能力标记** - 为每个模型标记功能：👁 视觉 | 🧠 推理 | 💬 对话 | 🎨 生图
- **按 Provider 分组** - 模型选择器按服务商分组显示，清晰直观
- **会话级绑定** - 每个对话可绑定不同的 Provider 和模型

### 👁 智能视觉识别系统

这是本项目的一大亮点——根据模型能力和用户选择，智能选择最优的文件处理方案：

#### 场景一：模型支持视觉功能
| 文件类型 | 处理方式 |
|---------|---------|
| **图片** | 直接发送给 AI，由模型识别内容 |
| **PDF/Word/PPT** | 先用工具提取文字 → 有文字则作为上下文发送 → 无文字则转图片（两页合并一张）直接发给 AI |

#### 场景二：模型不支持视觉，选择「不启用」
| 文件类型 | 处理方式 |
|---------|---------|
| **图片** | 不进行识别处理，直接跳过 |
| **PDF/Word/PPT** | 仅用工具提取文字，无文字则跳过 |

#### 场景三：模型不支持视觉，选择「本地 OCR」
| 文件类型 | 处理方式 |
|---------|---------|
| **图片** | 使用本地 OCR（RapidOCR）提取文字 |
| **PDF/Word/PPT** | 先用工具提取文字 → 有文字则作为上下文发送 → 无文字则用 OCR 识别 |

#### 场景四：模型不支持视觉，选择「视觉模型」
| 文件类型 | 处理方式 |
|---------|---------|
| **图片** | 发送给配置的视觉模型识别，将描述作为上下文发给对话模型 |
| **PDF/Word/PPT** | 转为图片（两页合并一张）→ 发给视觉模型识别 → 将识别结果作为上下文发给对话模型 |

> 💡 **巧思**：
> - 文档转图片时采用「两页合并一张」的策略，既能保持上下文连贯性，又能减少 API 调用次数，节省成本
> - 提供「不启用」选项是因为部分模型（如 DeepSeek）虽然不支持视觉输入，但自带 OCR 能力，可以直接处理文字

### 📚 知识库 (RAG)
- **多知识库管理** - 创建多个独立知识库，按主题分类
- **向量检索** - 支持 text-embedding-3-small 等向量模型
- **重排模型** - 可选配置 Rerank 模型提升检索精度
- **智能分块** - 自动将文档切分为语义完整的片段
- **图片识别** - 可选提取文档内嵌图片并用视觉模型识别

**支持格式**：PDF, Word (.doc/.docx), PPT (.pptx), Excel (.xlsx/.xls), TXT, Markdown, CSV, JSON, XML, HTML, 图片

### 🔧 MCP 工具调用
- **Model Context Protocol** - 支持标准 MCP 协议
- **双连接模式** - STDIO（本地进程）和 HTTP/SSE（远程服务）
- **工具选择器** - 可选择启用哪些 MCP 服务器
- **实时状态** - 显示服务器运行状态和可用工具

### 🌐 联网搜索
- **DuckDuckGo** - 免费搜索，无需 API Key
- **Tavily** - 高质量搜索，有免费额度
- **智能调用** - AI 根据问题自动判断是否需要搜索

### 🎨 图像生成
- **DALL-E 支持** - 兼容 OpenAI 图像生成 API
- **自定义尺寸** - 支持设置生成图片的宽高
- **生图模式** - 一键切换到生图模式

### 🧠 深度思考
- **推理模式** - 支持 DeepSeek R1、OpenAI o1/o3、Gemini 等推理模型
- **思考过程展示** - 流式显示模型的推理过程
- **自动识别** - 根据模型能力自动显示思考开关

### 💬 对话体验
- **流式输出** - 实时渲染 AI 回复
- **Token 统计** - 显示每条消息的 Token 消耗
- **Markdown 渲染** - 代码高亮、数学公式（KaTeX）、表格
- **对话管理** - 置顶、重命名、删除对话
- **自动命名** - 首条消息后自动生成对话标题
- **文件上传** - 支持拖拽上传，多文件支持

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

**可选依赖**（增强功能）：
```bash
# OCR 支持（本地文字识别）
pip install rapidocr-onnxruntime

# PDF 转图片（视觉识别 PDF）
pip install pdf2image
# Windows 还需安装 Poppler: https://github.com/oschwartz10612/poppler-windows/releases
```

### 2. 启动服务

```bash
python start.py
```

启动后会自动在浏览器中打开 http://localhost:8000

### 3. 配置 Provider

点击「⚙️ 设置」→「管理 Provider」，添加你的 AI 服务：

| 字段 | 说明 | 示例 |
|------|------|------|
| 名称 | Provider 显示名称 | `OpenAI` / `智谱AI` |
| API Base URL | API 服务地址 | `https://api.openai.com/v1` |
| API Key | 密钥 | `sk-xxx` |
| 默认模型 | 该 Provider 的默认模型 | `gpt-4o` |

为每个模型勾选其支持的能力：
- 👁 **视觉** - 支持图片输入
- 🧠 **推理** - 支持深度思考
- 💬 **对话** - 支持文本对话
- 🎨 **生图** - 支持图像生成

---

## 📖 功能详解

### 知识库使用

1. 「设置」→「管理知识库」→ 创建知识库
2. 选择向量模型（必选），可选配置重排模型和图片识别
3. 上传文档，等待处理完成
4. 对话时开启「📚」开关即可检索知识库

### MCP 工具使用

1. 「设置」→「管理 MCP」→ 添加服务器
2. 配置连接方式：
   - **STDIO**：填写命令和参数（如 `uvx mcp-server-time`）
   - **HTTP**：填写服务 URL
3. 点击「测试」验证连接
4. 对话时开启「🔧」开关，选择要使用的服务器

### 联网搜索配置

1. 「设置」→「配置联网搜索」
2. 选择默认搜索源
3. 如使用 Tavily，填入 API Key
4. 对话时开启「🌐」开关

### 图像生成

1. 配置一个生图模型（如 dall-e-3），勾选「🎨 生图」能力
2. 对话时点击「🎨」按钮开启生图模式
3. 设置图片尺寸
4. 输入描述即可生成

### 视觉识别配置

1. 「设置」→ 选择「默认视觉模型」
2. 当对话模型不支持视觉时，上传文件后会显示「👁️」按钮
3. 点击按钮可选择三种识别方式：
   - **不启用** - 不进行额外识别（适合自带 OCR 能力的模型）
   - **本地 OCR** - 使用 RapidOCR 本地识别文字
   - **视觉模型** - 使用配置的视觉模型识别图片内容

---

## 📁 项目结构

```
├── app/                        # 后端代码
│   ├── ai/                     # AI 模块
│   │   ├── ai_manager.py       # AI 调用管理器
│   │   ├── mcp_client.py       # MCP 客户端
│   │   ├── tools.py            # 工具定义（知识库、搜索）
│   │   └── knowledge_graph.py  # 知识图谱（实验性）
│   ├── core/                   # 核心配置
│   │   └── config.py           # 配置管理
│   ├── db/                     # 数据库
│   │   ├── models.py           # 数据模型
│   │   ├── crud.py             # 数据操作
│   │   └── database.py         # 数据库连接
│   ├── utils/                  # 工具函数
│   │   ├── document_parser.py  # 文档解析
│   │   ├── ocr.py              # OCR 识别
│   │   ├── context_manager.py  # 上下文管理
│   │   └── logger.py           # 日志记录
│   └── main.py                 # FastAPI 主应用
├── frontend/                   # 前端代码
│   ├── index.html              # 主页面
│   ├── script.js               # 主逻辑
│   ├── style.css               # 样式
│   ├── markdown.js             # Markdown 渲染
│   └── lib/                    # 第三方库
├── logs/                       # 日志目录
├── uploads/                    # 对话上传文件
├── uploaded_files/             # 知识库文件
├── start.py                    # 启动脚本
├── collect_logs.py             # 日志收集工具
└── requirements.txt            # 依赖列表
```

---

## 🔧 常见问题

### Q: 端口被占用？
修改 `start.py` 中的 `port=8000` 为其他端口。

### Q: API 调用失败？
1. 检查 Provider 配置，确保 API Base URL 和 API Key 正确
2. 查看「设置」→「导出日志」排查问题

### Q: OCR 识别不准确？
本地 OCR 使用 RapidOCR，对于复杂排版可能效果有限。建议：
1. 配置视觉模型（如 gpt-4o）
2. 勾选「👁️」按钮使用视觉模型识别

### Q: 如何重置数据？
```bash
# Windows
del app.db

# Linux/Mac
rm app.db

# 重启自动创建新数据库
python start.py
```

### Q: 如何导出日志？
「设置」→「导出日志」，或运行：
```bash
python collect_logs.py
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | FastAPI |
| **数据库** | SQLAlchemy + SQLite |
| **HTTP 客户端** | httpx |
| **文档解析** | PyPDF2, python-docx, python-pptx, openpyxl |
| **OCR** | RapidOCR (可选) |
| **PDF 转图片** | pdf2image + Poppler (可选) |
| **前端** | 原生 JavaScript |
| **Markdown** | Marked.js |
| **代码高亮** | Highlight.js |
| **数学公式** | KaTeX |
| **XSS 防护** | DOMPurify |

---

## 📄 许可证

MIT License

---

## 📮 联系方式

- GitHub Issues: [提交问题](https://github.com/vetisn/linga-chat/issues)
- 邮箱: 2414644363@qq.com

---

<div align="center">

> 本项目大部分代码由 AI 辅助完成，仅供学习研究使用。

**🔮 灵枢 · Linga Chat** - 让 AI 触手可及

</div>
