# 🚀 快速开始

## 3分钟启动本地AI助手

### 1️⃣ 安装依赖
```bash
pip install -r requirements.txt
```

### 2️⃣ 配置API
```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env 文件，填入你的API信息
# 必填项：
AI_API_BASE=https://api.openai.com/v1
AI_API_KEY=sk-your-api-key-here
AI_MODEL=gpt-4o-mini
```

### 3️⃣ 启动应用
```bash
python start.py
```

### 4️⃣ 开始使用
打开浏览器访问：http://localhost:8000

## 🔧 常见API配置

### OpenAI
```bash
AI_API_BASE=https://api.openai.com/v1
AI_API_KEY=sk-xxxxxxxxxxxxx
AI_MODEL=gpt-4o-mini
```

### 其他兼容OpenAI的服务
```bash
AI_API_BASE=https://your-api-provider.com/v1
AI_API_KEY=your-api-key
AI_MODEL=your-model-name
```

## ❓ 遇到问题？

- **依赖安装失败**：尝试使用 `pip install -r requirements.txt --upgrade`
- **API调用失败**：检查API密钥和网络连接
- **启动失败**：运行 `python check_deps.py` 检查依赖

### 🐛 反馈问题
如果问题仍未解决：
```bash
# 收集日志信息
python collect_logs.py

# 然后在GitHub提交Issue并附上日志文件
```

更多详细信息请查看 [README.md](README.md)