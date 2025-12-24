# app/db/crud.py
from __future__ import annotations

import json
from typing import List, Optional, Iterable, Tuple

from sqlalchemy.orm import Session

from app.db import models


def get_conversation(db: Session, conversation_id: int) -> Optional[models.Conversation]:
    return db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()


def get_conversations(db: Session) -> List[models.Conversation]:
    return (
        db.query(models.Conversation)
        .order_by(models.Conversation.is_pinned.desc(), models.Conversation.id.desc())
        .all()
    )


def get_latest_conversation(db: Session) -> Optional[models.Conversation]:
    return (
        db.query(models.Conversation)
        .order_by(models.Conversation.id.desc())
        .first()
    )


def get_conversation_message_count(db: Session, conversation_id: int) -> int:
    return (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .count()
    )


def create_conversation(
    db: Session,
    title: str = "新对话",
    model: Optional[str] = None,
) -> models.Conversation:
    conversation = models.Conversation(title=title, model=model)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation



def delete_conversation(db: Session, conversation_id: int) -> None:
    conversation = get_conversation(db, conversation_id)
    if conversation:
        db.delete(conversation)
        db.commit()


def update_conversation_title(db: Session, conversation_id: int, title: str) -> Optional[models.Conversation]:
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        return None
    conversation.title = title
    db.commit()
    db.refresh(conversation)
    return conversation


def update_conversation_model(db: Session, conversation_id: int, model: Optional[str]) -> Optional[models.Conversation]:
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        return None
    conversation.model = model
    db.commit()
    db.refresh(conversation)
    return conversation


def update_conversation_pin(db: Session, conversation_id: int, is_pinned: bool) -> Optional[models.Conversation]:
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        return None
    conversation.is_pinned = is_pinned
    db.commit()
    db.refresh(conversation)
    return conversation


def create_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    token_info: dict = None,
) -> models.Message:
    message_data = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content
    }
    
    # 如果是assistant消息且有token信息，则保存token统计
    if role == "assistant" and token_info:
        message_data.update({
            "model": token_info.get("model"),
            "input_tokens": token_info.get("input_tokens"),
            "output_tokens": token_info.get("output_tokens"),
            "total_tokens": token_info.get("total_tokens")
        })
    
    message = models.Message(**message_data)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_messages(db: Session, conversation_id: int) -> List[models.Message]:
    return (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.id.asc())
        .all()
    )


def create_uploaded_file(
    db: Session,
    conversation_id: int,
    filename: str,
    filepath: str,
) -> models.UploadedFile:
    uploaded_file = models.UploadedFile(conversation_id=conversation_id, filename=filename, filepath=filepath)
    db.add(uploaded_file)
    db.commit()
    db.refresh(uploaded_file)
    return uploaded_file


def get_uploaded_files(db: Session, conversation_id: int) -> List[models.UploadedFile]:
    return (
        db.query(models.UploadedFile)
        .filter(models.UploadedFile.conversation_id == conversation_id)
        .order_by(models.UploadedFile.id.desc())
        .all()
    )


def get_uploaded_file(db: Session, file_id: int) -> Optional[models.UploadedFile]:
    return db.query(models.UploadedFile).filter(models.UploadedFile.id == file_id).first()


def delete_uploaded_file(db: Session, file_id: int) -> None:
    uploaded_file = get_uploaded_file(db, file_id)
    if uploaded_file:
        db.delete(uploaded_file)
        db.commit()


# ========= 新增：会话扩展（Provider 绑定 & 功能开关） =========

def update_conversation_features(
    db: Session,
    conversation_id: int,
    *,
    enable_knowledge_base: Optional[bool] = None,
    enable_mcp: Optional[bool] = None,
    enable_web_search: Optional[bool] = None,
) -> Optional[models.Conversation]:
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        return None

    if enable_knowledge_base is not None:
        conversation.enable_knowledge_base = enable_knowledge_base
    if enable_mcp is not None:
        conversation.enable_mcp = enable_mcp
    if enable_web_search is not None:
        conversation.enable_web_search = enable_web_search

    db.commit()
    db.refresh(conversation)
    return conversation


def set_conversation_provider(
    db: Session,
    conversation_id: int,
    provider_id: Optional[int],
) -> Optional[models.Conversation]:
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        return None
    conversation.provider_id = provider_id
    db.commit()
    db.refresh(conversation)
    return conversation


# ========= 新增：Provider 相关 CRUD =========

def create_provider(
    db: Session,
    *,
    name: str,
    api_base: str,
    api_key: str,
    default_model: str,
    models_str: Optional[str] = None,
    is_default: bool = False,
) -> models.Provider:
    provider = models.Provider(
        name=name,
        api_base=api_base,
        api_key=api_key,
        default_model=default_model,
        models=models_str,
        is_default=is_default,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def get_provider(db: Session, provider_id: int) -> Optional[models.Provider]:
    return db.query(models.Provider).filter(models.Provider.id == provider_id).first()


def get_provider_by_name(db: Session, name: str) -> Optional[models.Provider]:
    return db.query(models.Provider).filter(models.Provider.name == name).first()


def list_providers(db: Session) -> List[models.Provider]:
    return db.query(models.Provider).order_by(models.Provider.id.asc()).all()


def update_provider(
    db: Session,
    provider_id: int,
    *,
    name: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    default_model: Optional[str] = None,
    models_str: Optional[str] = None,
    is_default: Optional[bool] = None,
) -> Optional[models.Provider]:
    provider = get_provider(db, provider_id)
    if not provider:
        return None

    if name is not None:
        provider.name = name
    if api_base is not None:
        provider.api_base = api_base
    if api_key is not None:
        provider.api_key = api_key
    if default_model is not None:
        provider.default_model = default_model
    if models_str is not None:
        provider.models = models_str
    if is_default is not None:
        provider.is_default = is_default

    db.commit()
    db.refresh(provider)
    return provider


def delete_provider(db: Session, provider_id: int) -> None:
    provider = get_provider(db, provider_id)
    if not provider:
        return
    db.delete(provider)
    db.commit()


# ========= 新增：知识库（多库）相关 CRUD =========

def create_knowledge_base(
    db: Session,
    *,
    name: str,
    description: Optional[str] = None,
) -> models.KnowledgeBase:
    kb = models.KnowledgeBase(name=name, description=description)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def get_knowledge_base(db: Session, kb_id: int) -> Optional[models.KnowledgeBase]:
    return db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()


def list_knowledge_bases(db: Session) -> List[models.KnowledgeBase]:
    return db.query(models.KnowledgeBase).order_by(models.KnowledgeBase.id.asc()).all()


def delete_knowledge_base(db: Session, kb_id: int) -> None:
    kb = get_knowledge_base(db, kb_id)
    if not kb:
        return
    db.delete(kb)
    db.commit()


def create_knowledge_document(
    db: Session,
    *,
    kb_id: Optional[int],
    file_name: str,
    file_path: str,
    content: Optional[str],
    embedding_model: Optional[str] = None,
) -> models.KnowledgeDocument:
    doc = models.KnowledgeDocument(
        kb_id=kb_id,
        file_name=file_name,
        file_path=file_path,
        content=content,
        embedding_model=embedding_model,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_knowledge_document(db: Session, doc_id: int) -> Optional[models.KnowledgeDocument]:
    return (
        db.query(models.KnowledgeDocument)
        .filter(models.KnowledgeDocument.id == doc_id)
        .first()
    )


def list_knowledge_documents(
    db: Session,
    kb_id: Optional[int] = None,
) -> List[models.KnowledgeDocument]:
    q = db.query(models.KnowledgeDocument)
    if kb_id is not None:
        q = q.filter(models.KnowledgeDocument.kb_id == kb_id)
    return q.order_by(models.KnowledgeDocument.id.desc()).all()


def delete_knowledge_document(db: Session, doc_id: int) -> None:
    doc = get_knowledge_document(db, doc_id)
    if not doc:
        return
    db.delete(doc)
    db.commit()


def create_knowledge_chunks(
    db: Session,
    *,
    document_id: int,
    chunks: Iterable[Tuple[int, str, List[float]]],
) -> List[models.KnowledgeChunk]:
    """
    批量创建知识库 chunk。
    chunks: (chunk_index, content, embedding) 列表
    """
    created: List[models.KnowledgeChunk] = []
    for idx, content, embedding in chunks:
        kc = models.KnowledgeChunk(
            document_id=document_id,
            chunk_index=idx,
            content=content,
            embedding=json.dumps(embedding, ensure_ascii=False),
        )
        db.add(kc)
        created.append(kc)
    db.commit()
    for kc in created:
        db.refresh(kc)
    return created


def list_chunks_by_document(
    db: Session,
    document_id: int,
) -> List[models.KnowledgeChunk]:
    return (
        db.query(models.KnowledgeChunk)
        .filter(models.KnowledgeChunk.document_id == document_id)
        .order_by(models.KnowledgeChunk.chunk_index.asc())
        .all()
    )


def list_all_chunks(
    db: Session,
    kb_id: Optional[int] = None,
) -> List[models.KnowledgeChunk]:
    """
    返回所有 chunk，如果 kb_id 不为空，则按知识库过滤：
    join KnowledgeDocument -> KnowledgeBase
    """
    q = db.query(models.KnowledgeChunk)
    if kb_id is not None:
        q = (
            q.join(
                models.KnowledgeDocument,
                models.KnowledgeChunk.document_id == models.KnowledgeDocument.id,
            )
            .filter(models.KnowledgeDocument.kb_id == kb_id)
        )
    return q.all()


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    import math

    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    na = math.sqrt(sum(a * a for a in vec_a))
    nb = math.sqrt(sum(b * b for b in vec_b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def search_knowledge_chunks(
    db: Session,
    *,
    query_embedding: List[float],
    kb_id: Optional[int] = None,
    top_k: int = 5,
) -> List[models.KnowledgeChunk]:
    """
    简易向量检索：在 Python 内做余弦相似度排序。
    后续如果接入专门的向量库，可以只改这里的实现。
    """
    all_chunks = list_all_chunks(db, kb_id=kb_id)
    scored: List[Tuple[float, models.KnowledgeChunk]] = []

    for chunk in all_chunks:
        try:
            emb = json.loads(chunk.embedding)
            if not isinstance(emb, list):
                continue
            score = _cosine_similarity(query_embedding, emb)
            scored.append((score, chunk))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


# ========= 新增：MCP服务器管理 CRUD =========

def create_mcp_server(
    db: Session,
    *,
    name: str,
    description: Optional[str] = None,
    connection_type: str,
    command: Optional[str] = None,
    args: Optional[str] = None,
    url: Optional[str] = None,
    env_vars: Optional[str] = None,
    is_enabled: bool = True,
) -> models.MCPServer:
    mcp_server = models.MCPServer(
        name=name,
        description=description,
        connection_type=connection_type,
        command=command,
        args=args,
        url=url,
        env_vars=env_vars,
        is_enabled=is_enabled,
    )
    db.add(mcp_server)
    db.commit()
    db.refresh(mcp_server)
    return mcp_server


def get_mcp_server(db: Session, server_id: int) -> Optional[models.MCPServer]:
    return db.query(models.MCPServer).filter(models.MCPServer.id == server_id).first()


def get_mcp_server_by_name(db: Session, name: str) -> Optional[models.MCPServer]:
    return db.query(models.MCPServer).filter(models.MCPServer.name == name).first()


def list_mcp_servers(db: Session, enabled_only: bool = False) -> List[models.MCPServer]:
    query = db.query(models.MCPServer)
    if enabled_only:
        query = query.filter(models.MCPServer.is_enabled == True)
    return query.order_by(models.MCPServer.id.asc()).all()


def update_mcp_server(
    db: Session,
    server_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    connection_type: Optional[str] = None,
    command: Optional[str] = None,
    args: Optional[str] = None,
    url: Optional[str] = None,
    env_vars: Optional[str] = None,
    is_enabled: Optional[bool] = None,
) -> Optional[models.MCPServer]:
    server = get_mcp_server(db, server_id)
    if not server:
        return None

    if name is not None:
        server.name = name
    if description is not None:
        server.description = description
    if connection_type is not None:
        server.connection_type = connection_type
    if command is not None:
        server.command = command
    if args is not None:
        server.args = args
    if url is not None:
        server.url = url
    if env_vars is not None:
        server.env_vars = env_vars
    if is_enabled is not None:
        server.is_enabled = is_enabled

    db.commit()
    db.refresh(server)
    return server


def delete_mcp_server(db: Session, server_id: int) -> None:
    server = get_mcp_server(db, server_id)
    if not server:
        return
    db.delete(server)
    db.commit()


# ========= 新增：系统设置管理 CRUD =========

def get_setting(db: Session, key: str) -> Optional[models.SystemSetting]:
    """获取单个设置"""
    return db.query(models.SystemSetting).filter(models.SystemSetting.key == key).first()


def get_all_settings(db: Session) -> List[models.SystemSetting]:
    """获取所有设置"""
    return db.query(models.SystemSetting).all()


def set_setting(db: Session, key: str, value: str) -> models.SystemSetting:
    """设置或更新设置值"""
    setting = get_setting(db, key)
    if setting:
        setting.value = value
        from datetime import datetime
        setting.updated_at = datetime.utcnow()
    else:
        setting = models.SystemSetting(key=key, value=value)
        db.add(setting)
    
    db.commit()
    db.refresh(setting)
    return setting


def delete_setting(db: Session, key: str) -> None:
    """删除设置"""
    setting = get_setting(db, key)
    if setting:
        db.delete(setting)
        db.commit()


# ========= 新增：知识图谱 CRUD =========

def create_entity(
    db: Session,
    *,
    kb_id: Optional[int] = None,
    document_id: Optional[int] = None,
    name: str,
    entity_type: str,
    description: Optional[str] = None,
    properties: Optional[str] = None,
) -> models.KnowledgeEntity:
    """创建知识图谱实体"""
    entity = models.KnowledgeEntity(
        kb_id=kb_id,
        document_id=document_id,
        name=name,
        entity_type=entity_type,
        description=description,
        properties=properties,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def get_entity(db: Session, entity_id: int) -> Optional[models.KnowledgeEntity]:
    """获取单个实体"""
    return db.query(models.KnowledgeEntity).filter(models.KnowledgeEntity.id == entity_id).first()


def get_entity_by_name(
    db: Session,
    name: str,
    kb_id: Optional[int] = None,
) -> Optional[models.KnowledgeEntity]:
    """根据名称获取实体"""
    q = db.query(models.KnowledgeEntity).filter(models.KnowledgeEntity.name == name)
    if kb_id is not None:
        q = q.filter(models.KnowledgeEntity.kb_id == kb_id)
    return q.first()


def list_entities(
    db: Session,
    kb_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    limit: int = 100,
) -> List[models.KnowledgeEntity]:
    """列出实体"""
    q = db.query(models.KnowledgeEntity)
    if kb_id is not None:
        q = q.filter(models.KnowledgeEntity.kb_id == kb_id)
    if entity_type is not None:
        q = q.filter(models.KnowledgeEntity.entity_type == entity_type)
    return q.order_by(models.KnowledgeEntity.id.desc()).limit(limit).all()


def search_entities(
    db: Session,
    query: str,
    kb_id: Optional[int] = None,
    limit: int = 10,
) -> List[models.KnowledgeEntity]:
    """搜索实体（模糊匹配名称和描述）"""
    q = db.query(models.KnowledgeEntity).filter(
        (models.KnowledgeEntity.name.ilike(f"%{query}%")) |
        (models.KnowledgeEntity.description.ilike(f"%{query}%"))
    )
    if kb_id is not None:
        q = q.filter(models.KnowledgeEntity.kb_id == kb_id)
    return q.limit(limit).all()


def delete_entity(db: Session, entity_id: int) -> None:
    """删除实体（会级联删除相关关系）"""
    entity = get_entity(db, entity_id)
    if entity:
        db.delete(entity)
        db.commit()


def create_relation(
    db: Session,
    *,
    kb_id: Optional[int] = None,
    source_id: int,
    target_id: int,
    relation_type: str,
    description: Optional[str] = None,
    weight: int = 1,
) -> models.KnowledgeRelation:
    """创建知识图谱关系"""
    relation = models.KnowledgeRelation(
        kb_id=kb_id,
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        description=description,
        weight=weight,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation


def get_relation(db: Session, relation_id: int) -> Optional[models.KnowledgeRelation]:
    """获取单个关系"""
    return db.query(models.KnowledgeRelation).filter(models.KnowledgeRelation.id == relation_id).first()


def list_relations(
    db: Session,
    kb_id: Optional[int] = None,
    entity_id: Optional[int] = None,
    relation_type: Optional[str] = None,
    limit: int = 100,
) -> List[models.KnowledgeRelation]:
    """列出关系"""
    q = db.query(models.KnowledgeRelation)
    if kb_id is not None:
        q = q.filter(models.KnowledgeRelation.kb_id == kb_id)
    if entity_id is not None:
        q = q.filter(
            (models.KnowledgeRelation.source_id == entity_id) |
            (models.KnowledgeRelation.target_id == entity_id)
        )
    if relation_type is not None:
        q = q.filter(models.KnowledgeRelation.relation_type == relation_type)
    return q.order_by(models.KnowledgeRelation.id.desc()).limit(limit).all()


def get_entity_relations(
    db: Session,
    entity_id: int,
    direction: str = "both",  # "outgoing", "incoming", "both"
) -> List[models.KnowledgeRelation]:
    """获取实体的所有关系"""
    if direction == "outgoing":
        return db.query(models.KnowledgeRelation).filter(
            models.KnowledgeRelation.source_id == entity_id
        ).all()
    elif direction == "incoming":
        return db.query(models.KnowledgeRelation).filter(
            models.KnowledgeRelation.target_id == entity_id
        ).all()
    else:
        return db.query(models.KnowledgeRelation).filter(
            (models.KnowledgeRelation.source_id == entity_id) |
            (models.KnowledgeRelation.target_id == entity_id)
        ).all()


def delete_relation(db: Session, relation_id: int) -> None:
    """删除关系"""
    relation = get_relation(db, relation_id)
    if relation:
        db.delete(relation)
        db.commit()


def get_related_entities(
    db: Session,
    entity_id: int,
    max_depth: int = 2,
    kb_id: Optional[int] = None,
) -> List[dict]:
    """
    获取与指定实体相关的所有实体（图遍历）
    返回格式: [{"entity": Entity, "relation": Relation, "depth": int}, ...]
    """
    visited = set()
    results = []
    
    def traverse(current_id: int, depth: int):
        if depth > max_depth or current_id in visited:
            return
        visited.add(current_id)
        
        relations = get_entity_relations(db, current_id)
        for rel in relations:
            # 确定相关实体
            related_id = rel.target_id if rel.source_id == current_id else rel.source_id
            if related_id not in visited:
                related_entity = get_entity(db, related_id)
                if related_entity and (kb_id is None or related_entity.kb_id == kb_id):
                    results.append({
                        "entity": related_entity,
                        "relation": rel,
                        "depth": depth,
                    })
                    traverse(related_id, depth + 1)
    
    traverse(entity_id, 1)
    return results


def batch_create_entities_and_relations(
    db: Session,
    *,
    kb_id: Optional[int] = None,
    document_id: Optional[int] = None,
    entities: List[dict],
    relations: List[dict],
) -> dict:
    """
    批量创建实体和关系
    entities: [{"name": str, "entity_type": str, "description": str}, ...]
    relations: [{"source": str, "target": str, "relation_type": str}, ...]
    """
    entity_map = {}  # name -> entity
    created_entities = []
    created_relations = []
    
    # 1. 创建或获取实体
    for ent_data in entities:
        name = ent_data.get("name", "").strip()
        if not name:
            continue
        
        # 检查是否已存在
        existing = get_entity_by_name(db, name, kb_id)
        if existing:
            entity_map[name] = existing
        else:
            entity = models.KnowledgeEntity(
                kb_id=kb_id,
                document_id=document_id,
                name=name,
                entity_type=ent_data.get("entity_type", "概念"),
                description=ent_data.get("description"),
                properties=json.dumps(ent_data.get("properties", {}), ensure_ascii=False) if ent_data.get("properties") else None,
            )
            db.add(entity)
            db.flush()  # 获取ID
            entity_map[name] = entity
            created_entities.append(entity)
    
    # 2. 创建关系
    for rel_data in relations:
        source_name = rel_data.get("source", "").strip()
        target_name = rel_data.get("target", "").strip()
        relation_type = rel_data.get("relation_type", "相关")
        
        if not source_name or not target_name:
            continue
        
        source = entity_map.get(source_name)
        target = entity_map.get(target_name)
        
        if source and target and source.id != target.id:
            # 检查是否已存在相同关系
            existing_rel = db.query(models.KnowledgeRelation).filter(
                models.KnowledgeRelation.source_id == source.id,
                models.KnowledgeRelation.target_id == target.id,
                models.KnowledgeRelation.relation_type == relation_type,
            ).first()
            
            if not existing_rel:
                relation = models.KnowledgeRelation(
                    kb_id=kb_id,
                    source_id=source.id,
                    target_id=target.id,
                    relation_type=relation_type,
                    description=rel_data.get("description"),
                    weight=rel_data.get("weight", 1),
                )
                db.add(relation)
                created_relations.append(relation)
    
    db.commit()
    
    return {
        "entities_created": len(created_entities),
        "relations_created": len(created_relations),
        "total_entities": len(entity_map),
    }


def get_knowledge_graph_stats(db: Session, kb_id: Optional[int] = None) -> dict:
    """获取知识图谱统计信息"""
    entity_query = db.query(models.KnowledgeEntity)
    relation_query = db.query(models.KnowledgeRelation)
    
    if kb_id is not None:
        entity_query = entity_query.filter(models.KnowledgeEntity.kb_id == kb_id)
        relation_query = relation_query.filter(models.KnowledgeRelation.kb_id == kb_id)
    
    entity_count = entity_query.count()
    relation_count = relation_query.count()
    
    # 统计实体类型分布
    type_stats = {}
    if entity_count > 0:
        from sqlalchemy import func
        type_counts = db.query(
            models.KnowledgeEntity.entity_type,
            func.count(models.KnowledgeEntity.id)
        )
        if kb_id is not None:
            type_counts = type_counts.filter(models.KnowledgeEntity.kb_id == kb_id)
        type_counts = type_counts.group_by(models.KnowledgeEntity.entity_type).all()
        type_stats = {t: c for t, c in type_counts}
    
    return {
        "entity_count": entity_count,
        "relation_count": relation_count,
        "entity_types": type_stats,
    }
