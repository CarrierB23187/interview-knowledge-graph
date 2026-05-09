"""Extract knowledge points and relations from documents using MiniMax M2.7 API.

Strategy: Process each document in full (or large chunks for docs > 25k chars)
instead of per-chapter, to minimize API calls (~12 total for 9 docs).
"""

import json
import os
import re
import time
from typing import Optional

import httpx

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_ENDPOINT = "https://api.minimaxi.com/v1/chat/completions"
MODEL = "MiniMax-M2.7"

SYSTEM_PROMPT = """你是一个面试知识点整理专家。你的任务是从面试题文档中提取所有知识点及其关联关系。

## 输出要求

1. **knowledgePoints**: 提取中等粒度的知识点（按主题/概念拆分）
   - id: 短横线分隔的英文标识符（如 jvm-gc-algorithm）
   - title: 知识点中文标题（简洁，<15字）
   - summary: 一句话概括核心内容（<60字）
   - parentId: 父级知识点 id，没有则为 null
   - tags: 2-4个分类标签
   - importance: 重要性 1-5（5为最高，面试高频考点）

2. **relations**: 知识点之间的关联关系
   - from / to: 知识点 id
   - type: 关系类型——prerequisite(前置知识)、contains(包含)、related(相关)、compare(对比)
   - description: 关系简述（<20字）

## 输出格式（严格 JSON）

```json
{
  "knowledgePoints": [
    {
      "id": "jvm-gc",
      "title": "GC 垃圾回收",
      "summary": "JVM 垃圾回收的三种核心算法及常用收集器",
      "parentId": "jvm-memory",
      "tags": ["JVM", "GC"],
      "importance": 5
    }
  ],
  "relations": [
    {
      "from": "jvm-gc",
      "to": "jvm-memory",
      "type": "prerequisite",
      "description": "理解GC需要先了解内存模型"
    }
  ]
}
```

注意：
- 只输出 JSON，不要有任何额外文字
- 确保 JSON 格式完全正确
- 从文档中提取 8-20 个知识点
- 知识点之间尽量多建立关联"""


def chunk_text(text: str, max_chars: int = 25000) -> list[str]:
    """Split text into chunks of max_chars, trying to break at newlines."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    while len(text) > max_chars:
        split_at = text.rfind("\n", 0, max_chars)
        if split_at == -1:
            split_at = max_chars
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()

    if text:
        chunks.append(text)

    return chunks


def call_minimax(system_prompt: str, user_prompt: str, max_retries: int = 3) -> Optional[dict]:
    """Call MiniMax M2.7 API and return parsed JSON response."""
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }

    for attempt in range(max_retries):
        try:
            response = httpx.post(
                MINIMAX_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=180.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if json_match:
                content = json_match.group(1).strip()

            result = json.loads(content)
            usage = data.get("usage", {})
            print(f"      tokens: {usage.get('total_tokens', '?')}")
            return result

        except (json.JSONDecodeError, KeyError) as e:
            print(f"    Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(3 ** attempt)
        except httpx.HTTPError as e:
            print(f"    HTTP error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(3 ** attempt)

    return None


def extract_from_document(doc: dict, global_id_prefix: str) -> dict:
    """Extract knowledge points from a single document.

    Processes the document in chunks if needed, then merges results.
    """
    file_name = doc["fileName"]
    full_text = doc.get("fullText", "")

    if len(full_text) < 100:
        print(f"    Skipping '{file_name}' (too short: {len(full_text)} chars)")
        return {"fileName": file_name, "knowledgePoints": [], "relations": []}

    chunks = chunk_text(full_text)
    print(f"    {file_name}: {len(full_text)} chars → {len(chunks)} chunk(s)")

    all_kps = []
    all_relations = []

    for ci, chunk in enumerate(chunks):
        chunk_label = f" (part {ci + 1}/{len(chunks)})" if len(chunks) > 1 else ""
        print(f"      Chunk {ci + 1}{chunk_label}: {len(chunk)} chars...")

        user_prompt = f"""文档：{file_name}
文档内容：
{chunk[:25000]}"""

        result = call_minimax(SYSTEM_PROMPT, user_prompt)

        if result:
            kps = result.get("knowledgePoints", [])
            relations = result.get("relations", [])

            # Add source and prefix to IDs
            for kp in kps:
                kp["id"] = f"{global_id_prefix}-{kp['id']}"
                kp["source"] = file_name
                if kp.get("parentId") and global_id_prefix:
                    kp["parentId"] = f"{global_id_prefix}-{kp['parentId']}"

            for rel in relations:
                rel["from"] = f"{global_id_prefix}-{rel['from']}"
                rel["to"] = f"{global_id_prefix}-{rel['to']}"

            all_kps.extend(kps)
            all_relations.extend(relations)
            print(f"        → {len(kps)} KPs, {len(relations)} relations")

        if len(chunks) > 1 and ci < len(chunks) - 1:
            time.sleep(1.5)

    return {
        "fileName": file_name,
        "knowledgePoints": all_kps,
        "relations": all_relations,
    }


def extract_from_documents(docs: list[dict]) -> dict:
    """Process all documents sequentially."""
    all_nodes = []
    all_edges = []
    seen_ids = set()

    for i, doc in enumerate(docs):
        file_name = doc["fileName"]
        base_name = file_name.rsplit(".", 1)[0]
        prefix = re.sub(r"[^a-zA-Z0-9\-_]", "-", base_name).lower()

        print(f"\n[{i + 1}/{len(docs)}] {file_name}")
        result = extract_from_document(doc, prefix)

        for kp in result["knowledgePoints"]:
            if kp["id"] not in seen_ids:
                seen_ids.add(kp["id"])
                all_nodes.append(kp)

        for edge in result["relations"]:
            all_edges.append(edge)

        # Rate limiting between documents
        if i < len(docs) - 1:
            time.sleep(2)

    return {"nodes": all_nodes, "edges": all_edges}


if __name__ == "__main__":
    import sys

    input_file = sys.argv[1] if len(sys.argv) > 1 else "../output/parsed_docs.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "../output/extracted_knowledge.json"

    if not MINIMAX_API_KEY:
        print("ERROR: MINIMAX_API_KEY environment variable not set.")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        docs = json.load(f)

    print(f"Loaded {len(docs)} documents for AI extraction")
    print(f"Model: {MODEL}")
    print(f"Total chars across all docs: {sum(len(d.get('fullText','')) for d in docs)}")
    print()

    result = extract_from_documents(docs)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Extraction complete!")
    print(f"  Knowledge points: {len(result['nodes'])}")
    print(f"  Relations: {len(result['edges'])}")
    print(f"  Output: {output_file}")
