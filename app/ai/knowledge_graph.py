# app/ai/knowledge_graph.py
"""
知识图谱提取模块
使用 LLM 从文本中提取实体和关系
"""
import json
import re
from typing import List, Dict, Any, Optional, Tuple


# 实体提取的系统提示
ENTITY_EXTRACTION_PROMPT = """你是一个知识图谱构建专家。请从给定的文本中提取实体和关系。

## 实体类型
- 人物：人名、角色
- 组织：公司、团队、机构
- 技术：编程语言、框架、工具、库
- 概念：抽象概念、术语、方法论
- 产品：软件、服务、产品名
- 地点：地名、位置
- 时间：日期、时间段
- 其他：无法归类的实体

## 关系类型
- 属于：A 属于 B
- 包含：A 包含 B
- 使用：A 使用 B
- 依赖：A 依赖 B
- 创建：A 创建了 B
- 开发：A 开发了 B
- 相关：A 与 B 相关
- 对比：A 与 B 对比/竞争
- 继承：A 继承自 B
- 实现：A 实现了 B

## 输出格式
请严格按照以下 JSON 格式输出，不要添加任何其他内容：

```json
{
  "entities": [
    {"name": "实体名称", "entity_type": "实体类型", "description": "简短描述"}
  ],
  "relations": [
    {"source": "源实体名称", "target": "目标实体名称", "relation_type": "关系类型"}
  ]
}
```

## 注意事项
1. 只提取文本中明确提到的实体和关系
2. 实体名称要准确，不要缩写
3. 每个实体只出现一次
4. 关系要有明确的方向性
5. 如果文本太短或没有有意义的实体，返回空数组
"""


def build_extraction_messages(text: str, max_length: int = 2000) -> List[Dict[str, str]]:
    """构建提取实体关系的消息"""
    # 截断过长的文本
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return [
        {"role": "system", "content": ENTITY_EXTRACTION_PROMPT},
        {"role": "user", "content": f"请从以下文本中提取实体和关系：\n\n{text}"}
    ]


def parse_extraction_result(response: str) -> Tuple[List[Dict], List[Dict]]:
    """解析 LLM 返回的提取结果"""
    entities = []
    relations = []
    
    try:
        # 尝试提取 JSON 块
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析整个响应
            json_str = response
        
        # 清理可能的问题字符
        json_str = json_str.strip()
        
        data = json.loads(json_str)
        
        if isinstance(data, dict):
            entities = data.get("entities", [])
            relations = data.get("relations", [])
            
            # 验证实体格式
            valid_entities = []
            for ent in entities:
                if isinstance(ent, dict) and ent.get("name"):
                    valid_entities.append({
                        "name": str(ent.get("name", "")).strip(),
                        "entity_type": str(ent.get("entity_type", "概念")).strip(),
                        "description": str(ent.get("description", "")).strip() if ent.get("description") else None,
                    })
            entities = valid_entities
            
            # 验证关系格式
            valid_relations = []
            for rel in relations:
                if isinstance(rel, dict) and rel.get("source") and rel.get("target"):
                    valid_relations.append({
                        "source": str(rel.get("source", "")).strip(),
                        "target": str(rel.get("target", "")).strip(),
                        "relation_type": str(rel.get("relation_type", "相关")).strip(),
                    })
            relations = valid_relations
            
    except json.JSONDecodeError:
        # JSON 解析失败，尝试简单提取
        pass
    except Exception:
        pass
    
    return entities, relations


def extract_entities_from_text(
    text: str,
    ai_manager,
    model: Optional[str] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    从文本中提取实体和关系
    
    Args:
        text: 要提取的文本
        ai_manager: AI 管理器实例
        model: 使用的模型（可选）
    
    Returns:
        (entities, relations) 元组
    """
    if not text or len(text.strip()) < 10:
        return [], []
    
    messages = build_extraction_messages(text)
    
    try:
        result = ai_manager.chat(messages, model=model, stream=False)
        content = result.get("content", "")
        return parse_extraction_result(content)
    except Exception as e:
        print(f"知识图谱提取失败: {e}")
        return [], []


def extract_from_chunks(
    chunks: List[str],
    ai_manager,
    model: Optional[str] = None,
    batch_size: int = 3,
) -> Tuple[List[Dict], List[Dict]]:
    """
    从多个文本块中提取实体和关系
    
    Args:
        chunks: 文本块列表
        ai_manager: AI 管理器实例
        model: 使用的模型
        batch_size: 每批处理的块数
    
    Returns:
        合并后的 (entities, relations) 元组
    """
    all_entities = []
    all_relations = []
    entity_names = set()
    
    # 分批处理
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        combined_text = "\n\n---\n\n".join(batch)
        
        entities, relations = extract_entities_from_text(
            combined_text, ai_manager, model
        )
        
        # 去重合并实体
        for ent in entities:
            name = ent.get("name", "").lower()
            if name and name not in entity_names:
                entity_names.add(name)
                all_entities.append(ent)
        
        # 合并关系
        all_relations.extend(relations)
    
    return all_entities, all_relations


def search_graph_context(
    db,
    query: str,
    kb_id: Optional[int] = None,
    max_entities: int = 5,
    max_depth: int = 2,
) -> str:
    """
    基于查询搜索知识图谱，返回相关上下文
    
    Args:
        db: 数据库会话
        query: 查询文本
        kb_id: 知识库 ID
        max_entities: 最大返回实体数
        max_depth: 图遍历深度
    
    Returns:
        格式化的知识图谱上下文字符串
    """
    from app.db import crud
    
    # 1. 搜索匹配的实体
    matched_entities = crud.search_entities(db, query, kb_id, limit=max_entities)
    
    if not matched_entities:
        return ""
    
    context_parts = []
    context_parts.append("【知识图谱相关信息】")
    
    for entity in matched_entities:
        # 实体信息
        entity_info = f"\n■ {entity.name}（{entity.entity_type}）"
        if entity.description:
            entity_info += f"\n  描述：{entity.description}"
        context_parts.append(entity_info)
        
        # 获取相关实体和关系
        related = crud.get_related_entities(db, entity.id, max_depth=max_depth, kb_id=kb_id)
        
        if related:
            relations_info = []
            for item in related[:10]:  # 限制数量
                rel = item["relation"]
                related_ent = item["entity"]
                
                if rel.source_id == entity.id:
                    relations_info.append(f"  → {rel.relation_type} → {related_ent.name}")
                else:
                    relations_info.append(f"  ← {rel.relation_type} ← {related_ent.name}")
            
            if relations_info:
                context_parts.append("  关系：")
                context_parts.extend(relations_info)
    
    return "\n".join(context_parts)
