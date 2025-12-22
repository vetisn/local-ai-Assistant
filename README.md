# 本地 AI 助手 WebUI

一个功能强大、性能优化的本地AI助手Web界面，支持多模型、知识库、MCP工具调用、联网搜索等高级功能。

> 📖 **快速开始**: 查看 [QUICKSTART.md](QUICKSTART.md) 3分钟快速启动指南

## ✨ 主要特性

### 🚀 核心功能
- **多模型支持**：支持配置多个AI服务提供商和模型
- **流式输出**：优化的流式渲染机制，支持实时Token输出
- **对话管理**：支持多对话、对话置顶、重命名、删除等操作
- **Markdown渲染**：完整支持Markdown语法，包括代码高亮、表格、列表等
- **代码复制**：代码块一键复制功能

### 🧠 高级功能
- **知识库（RAG）**：支持文档上传、向量化存储、智能检索
  - 支持多种文件格式（PDF、Word、TXT、Markdown等）
  - 支持图片OCR识别（需配置视觉模型）
  - 支持重排模型提升检索精度
- **MCP工具调用**：支持Model Context Protocol工具集成
- **联网搜索**：支持Bing、Google等搜索引擎集成
- **多Provider管理**：灵活配置多个API提供商

### 🎨 界面特性
- **响应式设计**：适配桌面和移动设备
- **主题支持**：支持多种主题风格
- **字体大小调节**：可自定义界面字体大小
- **间距风格**：支持紧凑、正常、宽松三种间距风格
- **Token统计**：实时显示输入/输出Token消耗

### ⚡ 性能优化
- **批量渲染**：Token批量处理机制，大幅提升渲染性能
- **节流机制**：滚动和渲染节流，减少DOM操作
- **日志控制**：可控的调试日志输出
- **防串台机制**：切换对话时自动清理状态，避免内容混乱

## 📋 系统要求

- Python 3.8+
- 现代浏览器（Chrome、Firefox、Safari、Edge等）
- 至少512MB可用内存

## 🔧 安装步骤

### 1. 克隆项目
```bash
git clone <repository-url>
cd <project-directory>
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
复制 `.env.example` 为 `.env` 并配置你的API信息：
```bash
cp .env.example .env
# 然后编辑 .env 文件，填入你的API配置
```

示例配置：
```bash
# AI API 配置
AI_API_BASE=https://api.openai.com/v1
AI_API_KEY=sk-xxxxxxxxxxxxx
AI_MODEL=gpt-4o-mini
AI_MODELS=gpt-4o,gpt-4o-mini,gpt-3.5-turbo

# 向量模型配置（用于知识库功能）
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_MODELS=text-embedding-3-small,text-embedding-3-large
```

### 4. 启动应用
```bash
python start.py
```

**可选：检查依赖**
```bash
# 检查当前环境的依赖安装情况
python check_deps.py
```

应用将在 `http://localhost:8000` 启动。

## 📖 使用指南

### 基础使用

1. **创建对话**：点击左侧"新对话"按钮创建新的对话
2. **选择模型**：在顶部下拉菜单中选择要使用的AI模型
3. **发送消息**：在底部输入框输入消息，按Enter或点击发送按钮
4. **查看回复**：AI回复将以流式方式实时显示

### Provider管理

1. 点击右上角设置按钮
2. 选择"管理Provider"
3. 添加新的Provider：
   - 名称：Provider的显示名称
   - API Base：API基础地址
   - API Key：API密钥
   - 默认模型：该Provider的默认模型
   - 模型列表：配置可用模型及其能力（视觉、推理、对话）

### 知识库功能

#### 创建知识库

1. 点击设置 → 管理知识库
2. 点击"创建知识库"
3. 填写知识库信息：
   - 名称：知识库的显示名称
   - 描述：知识库的用途说明
   - 向量模型：用于文本向量化的模型
   - 视觉模型（可选）：用于图片OCR识别
   - 重排模型（可选）：用于提升检索精度

#### 上传文档

1. 选择已创建的知识库
2. 点击"上传文档"
3. 选择文件（支持PDF、Word、TXT、Markdown、图片等）
4. 等待处理完成

#### 使用知识库

1. 在对话界面开启"知识库"开关
2. 系统会自动从知识库中检索相关内容
3. AI将基于检索到的内容回答问题

### MCP工具调用

1. 点击设置 → 管理MCP服务器
2. 添加MCP服务器：
   - 名称：服务器名称
   - 连接类型：stdio或http
   - 配置相应的连接参数
3. 在对话中开启"MCP"开关
4. AI将自动调用相关工具

### 联网搜索

1. 点击设置 → 管理搜索密钥
2. 配置搜索引擎API密钥（Bing或Google）
3. 在对话中开启"联网"开关
4. 选择搜索源（Bing或Google）
5. AI将自动搜索并引用网络信息

## 🎯 高级配置

### 性能调优

在 `frontend/script.js` 中可以调整流式渲染参数：

```javascript
// 流式渲染配置
const STREAM_FLUSH_INTERVAL_MS = 80;   // 批量渲染间隔（毫秒）
const STREAM_FLUSH_MIN_CHARS = 120;    // 批量渲染最小字符数
```

- 增大参数：更快但"跳字"更明显
- 减小参数：更丝滑但更耗CPU

### 调试模式

在 `frontend/script.js` 中开启调试模式：

```javascript
const DEBUG_STREAM = true;  // 开启流式输出调试日志
```

### 数据库重置

如果需要重置数据库（清除所有数据）：

```bash
# 停止应用，然后删除数据库文件
rm app.db
# 重新启动应用会自动创建新的数据库
python start.py
```

## 📁 项目结构

```
.
├── app/                    # 后端应用
│   ├── ai/                # AI相关模块
│   │   ├── ai_manager.py  # AI管理器
│   │   └── tools.py       # 工具函数
│   ├── core/              # 核心配置
│   │   └── config.py      # 配置管理
│   ├── db/                # 数据库模块
│   ├── utils/             # 工具函数
│   └── main.py            # 主应用入口
├── frontend/              # 前端界面
│   ├── index.html         # 主页面
│   ├── script.js          # 主要逻辑
│   ├── style.css          # 样式文件
│   └── favicon.ico        # 网站图标
├── logs/                  # 日志目录
│   ├── README.md         # 日志说明文档
│   ├── main.log          # 系统主日志
│   ├── api.log           # API请求日志
│   ├── chat.log          # 对话日志
│   ├── token.log         # Token使用日志
│   ├── database.log      # 数据库操作日志
│   └── error.log         # 错误日志
├── uploaded_files/        # 知识库文件存储
├── uploads/               # 临时上传目录
├── .env.example           # 环境变量配置模板
├── .gitignore            # Git忽略文件
├── check_deps.py         # 依赖检查脚本
├── collect_logs.py       # 日志收集脚本
├── requirements.txt       # 项目依赖包
├── start.py              # 启动脚本
├── QUICKSTART.md         # 快速开始指南
└── README.md             # 本文档
```

## 🐛 问题反馈

如果遇到问题，请按以下步骤收集信息并反馈：

### 1. 收集日志信息
```bash
# 自动收集最近24小时的日志
python collect_logs.py

# 或手动查看特定日志
cat logs/error.log    # 查看错误日志
cat logs/main.log     # 查看系统日志
```

### 2. 反馈渠道
- **GitHub Issues**: [提交问题](https://github.com/your-repo/issues)
- **邮件**: your-email@example.com

### 3. 反馈信息
请提供以下信息：
- 问题的详细描述
- 重现步骤
- 系统环境（操作系统、Python版本）
- 日志文件（使用 `collect_logs.py` 生成）

### 4. 日志说明
- 系统会自动脱敏API密钥等敏感信息
- 但对话内容仍会被记录，请注意隐私保护
- 详细的日志说明请查看 [logs/README.md](logs/README.md)

## 🔍 常见问题
A: 检查端口8000是否被占用，可以在 `start.py` 中修改端口号。

### Q: API调用失败？
A: 检查 `.env` 文件中的API配置是否正确，确保API密钥有效且有足够余额。

### Q: 知识库上传失败？
A: 确保配置了正确的向量模型，检查文件格式是否支持。项目已包含所有文档处理依赖。

### Q: 缺少某些功能？
A: 项目已包含所有功能的依赖包。如果遇到问题，请检查：
- Python版本是否为3.8+
- 是否正确安装了所有依赖：`pip install -r requirements.txt`
- 对于OCR功能，需要额外安装Tesseract：[安装指南](https://github.com/tesseract-ocr/tesseract)

### Q: 流式输出很慢？
A: 这通常是网络问题或API响应慢导致的。如果是渲染慢，可以调整 `STREAM_FLUSH_INTERVAL_MS` 参数。

### Q: 数据库出现问题怎么办？
A: 如果遇到数据库相关错误，可以重置数据库：
```bash
# 停止应用，删除数据库文件
rm app.db  # Windows用户使用: del app.db
# 重新启动会自动创建新数据库
python start.py
```

### Q: 如何备份数据？
A: 数据库文件位于项目根目录的 `app.db`，直接复制此文件即可备份所有对话和设置。

### Q: 代码块显示异常？
A: 确保浏览器已加载 marked.js 和 DOMPurify 库，检查网络连接。

### Q: 切换对话后内容混乱？
A: 这个问题已通过防串台机制解决。如果仍然出现，请刷新页面。

## 🛠️ 技术栈

### 后端
- **FastAPI**：现代、快速的Web框架
- **SQLAlchemy**：ORM数据库操作
- **Python-dotenv**：环境变量管理
- **Requests**：HTTP请求库

### 前端
- **原生JavaScript**：无框架依赖，轻量高效
- **Marked.js**：Markdown解析
- **DOMPurify**：XSS防护
- **Highlight.js**：代码高亮（通过Marked集成）

### 数据库
- **SQLite**：轻量级嵌入式数据库

## 🔐 安全建议

1. **API密钥保护**：不要将 `.env` 文件提交到版本控制系统
2. **HTTPS部署**：生产环境建议使用HTTPS
3. **访问控制**：如需公网访问，建议添加身份认证
4. **定期备份**：定期备份 `app.db` 数据库文件
5. **日志审查**：定期检查 `logs/` 目录中的日志文件

## 📝 开发说明

### 添加新功能

1. 后端API：在 `app/main.py` 中添加新的路由
2. 前端界面：在 `frontend/script.js` 中添加相应逻辑
3. 样式调整：在 `frontend/style.css` 中修改样式

### 调试技巧

1. 后端调试：查看 `logs/` 目录中的日志文件
2. 前端调试：打开浏览器开发者工具（F12）查看控制台
3. 网络调试：在开发者工具的Network标签查看API请求

### 性能监控

- 查看 `logs/api.log` 了解API调用情况
- 查看 `logs/token.log` 了解Token消耗
- 使用浏览器性能分析工具监控前端性能

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 📄 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代Python Web框架
- [Marked.js](https://marked.js.org/) - Markdown解析器
- [DOMPurify](https://github.com/cure53/DOMPurify) - XSS防护库
- 所有贡献者和用户的支持

## 📮 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 提交Issue：[GitHub Issues](https://github.com/your-repo/issues)
- 邮件：your-email@example.com

---

**注意**：本项目仅供学习和研究使用，请遵守相关AI服务提供商的使用条款。
