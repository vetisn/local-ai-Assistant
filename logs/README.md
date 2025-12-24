# 日志目录

此目录存放应用运行日志，用于问题排查。

## 日志文件说明

| 文件 | 说明 |
|------|------|
| `main.log` | 主程序日志 |
| `chat.log` | 对话相关日志 |
| `api.log` | API 调用日志 |
| `error.log` | 错误日志 |
| `database.log` | 数据库操作日志 |
| `token.log` | Token 使用统计 |

## 收集日志

运行 `python collect_logs.py` 可打包所有日志用于问题排查。
