# 本地 AI 助手 WebUI

一个功能强大、轻量级的本地 AI 助手 Web 界面，支持多模型切换、知识库、MCP 工具调用、联网搜索等高级功能。

## ✨ 主要特性

### 🚀 核心功能
- **多模型支持**：兼容 OpenAI API 格式，支持配置多个 Provider
- **流式输出**：实时流式渲染，支持 Token 统计
- **对话管理**：多对话、置顶、重命名、删除等操作
- **Markdown 渲染**：完整支持 Markdown 语法，代码高亮、表格、列表等
- **代码复制**：代码块一键复制功能

### 🧠 高级功能
- **知识库（RAG）**：文档上传、向量化存储、智能检索
- **MCP 工具调用**：支持 Model Context Protocol 工具集成
- **联网搜索**：支持 DuckDuckGo（免费）和 Tavily 搜索引擎

### 🎨 界面特性
- **响应式设计**：适配桌面和移动设备
- **字体大小调节**：可自定义界面字体
- **间距风格**：紧凑 / 标准 / 宽松三种风格
- **Token 统计**：实时显示输入/输出 Token 消耗

## 📋 系统要求

- Python 3.8+
- 现代浏览器（Chrome、Firefox、Safari、Edge）

## 🔧 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/vetisn/local-ai-assistant.git
cd local-ai-assistant
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

编辑 `.env` 文件，填入你的 API 配置：

```bash
# AI API 配置
AI_API_BASE=https://api.openai.com/v1
AI_API_KEY=sk-xxxxxxxxxxxxx
AI_MODEL=gpt-4o-mini
AI_MODELS=gpt-4o-mini,gpt-4o,gpt-3.5-turbo

# 向量模型配置（知识库功能）
EMBEDDING_MODEL=text-embedding-3-small
```

### 4. 启动应用

```bash
python start.py
```

应用将在 http://localhost:8000 启动。

## 📖 使用指南

### 基础使用

1. **创建对话**：点击左侧「新对话」按钮
2. **选择模型**：在顶部下拉菜单选择 AI 模型
3. **发送消息**：输入消息，按 Enter 或点击发送
4. **流式输出**：AI 回复将实时显示

### Provider 管理

支持配置多个 API 提供商，方便切换不同的模型服务：

1. 点击「设置」→「管理 Provider」
2. 添加 Provider：填写名称、API Base、API Key、模型列表
3. 可为每个模型标记能力（视觉、推理、对话）

### 知识库功能

基于向量检索 + 知识图谱的本地知识库：

1. 「设置」→「管理知识库」→ 创建知识库
2. 上传文档（支持 TXT、Markdown、CSV）
3. 系统自动提取实体和关系，构建知识图谱
4. 对话时开启「知识库」开关，AI 将基于向量搜索 + 图谱关系回答

#### 知识图谱特性

- 自动从文档中提取实体（人物、技术、概念、组织等）
- 自动识别实体间的关系（依赖、包含、使用等）
- 检索时结合向量相似度 + 图谱关系，提升准确性
- 无需额外配置，上传文档时自动构建

#### 🚀 推荐：本地 RAG MCP（无需 API Key）

如果没有向量模型 API，推荐使用 [mcp-local-rag](https://github.com/shinpr/mcp-local-rag)：

- 完全本地运行，隐私优先
- 支持 PDF、DOCX、TXT、Markdown
- 语义搜索，理解自然语言
- 离线可用，零成本

配置方法：在「管理 MCP」中添加：

```json
{
  "name": "local-rag",
  "connection_type": "stdio",
  "command": "npx",
  "args": ["-y", "mcp-local-rag"]
}
```

### MCP 工具调用

支持 Model Context Protocol 工具集成：

1. 「设置」→「管理 MCP」→ 添加服务器
2. 支持 STDIO 和 HTTP 两种连接方式
3. 对话时开启「MCP」开关

### 联网搜索

支持实时联网搜索：

1. 默认使用 DuckDuckGo（免费，无需 API Key）
2. 可选配置 Tavily API Key 获得更好的搜索效果
3. 对话时开启「联网搜索」开关，AI 将自动搜索最新信息

## 📁 项目结构

```
├── app/                    # 后端代码
│   ├── ai/                 # AI 模块
│   │   ├── ai_manager.py   # AI 管理器
│   │   └── tools.py        # 工具函数
│   ├── core/               # 核心配置
│   ├── db/                 # 数据库模块
│   ├── utils/              # 工具函数
│   └── main.py             # FastAPI 入口
├── frontend/               # 前端代码
│   ├── index.html          # 主页面
│   ├── script.js           # 主逻辑
│   ├── style.css           # 样式
│   └── markdown.js         # Markdown 渲染
├── logs/                   # 日志目录
├── uploads/                # 上传文件目录
├── .env                    # 环境变量配置
├── start.py                # 启动脚本
├── collect_logs.py         # 日志收集
└── requirements.txt        # Python 依赖
```

## 🔍 常见问题

### Q: 端口被占用？

修改 `start.py` 中的端口号，或关闭占用 8000 端口的程序。

### Q: API 调用失败？

检查 `.env` 中的 API 配置是否正确，确保 API Key 有效。

### Q: 如何重置数据库？

```bash
rm app.db        # 删除数据库文件
python start.py  # 重启会自动创建新数据库
```

### Q: 如何备份数据？

直接复制 `app.db` 文件即可备份所有对话和设置。

## 🐛 问题反馈

如遇问题，请收集日志后反馈：

```bash
python collect_logs.py
```

或在 Web 界面「设置」→「导出日志」下载日志文件。

## 🛠️ 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite
- **前端**：原生 JavaScript + Marked.js + Highlight.js
- **HTTP**：httpx（AI API）+ requests（联网搜索）

## 🔐 安全建议

1. 不要将 `.env` 文件提交到版本控制
2. 生产环境建议使用 HTTPS
3. 公网访问建议添加身份认证
4. 定期备份 `app.db` 数据库文件

## 📄 许可证

MIT License

## 📮 联系方式

- GitHub Issues：[提交问题](https://github.com/vetisn/local-ai-Assistant/issues)
- 个人邮箱：2414644363@qq.com
---

**声明**：本项目大部分代码由 AI 辅助完成，仅供学习和研究使用。


