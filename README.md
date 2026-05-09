# 面试知识点图谱

从 PDF / Word 文档中自动提取知识结构，以**思维导图**和**知识图谱**双视图可视化展示，助力面试复习。

## 在线预览

👉 **[打开知识图谱](https://carrierb23187.github.io/interview-knowledge-graph/)**

## 功能特性

- **双视图联动**：左侧思维导图（层级浏览）+ 右侧知识图谱（网状探索）
- **AI 驱动**：利用 MiniMax M2.7 自动从文档中提取知识点和关联关系
- **交互丰富**：节点点击查看详情、搜索过滤、拖拽缩放、关联高亮
- **纯静态**：无需后端服务，GitHub Pages 即可部署

## 项目结构

```
├── docs/                        # 前端页面（GitHub Pages 部署目录）
│   ├── index.html               # 可视化主页面
│   └── knowledge-data.json      # 知识图谱数据
├── scripts/
│   ├── parse_pdf.py             # PDF 解析（PyMuPDF）
│   ├── parse_docx.py            # Word 解析（python-docx）
│   ├── extract_knowledge.py     # MiniMax M2.7 AI 知识提取
│   ├── merge_graph.py           # 去重合并 + 跨文档关联推断
│   ├── build.py                 # 一键构建脚本
│   └── generate_sample.py       # 生成示例数据（无需 API）
└── requirements.txt
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备文档

将 PDF / Word 文件放入项目根目录下的文档文件夹中。

### 3. 运行构建

```bash
export MINIMAX_API_KEY=your-api-key
python scripts/build.py <文档文件夹路径> docs/
```

### 4. 查看结果

```bash
# 本地预览
cd docs && python -m http.server 8765
# 打开 http://localhost:8765
```

## 数据模型

```json
{
  "nodes": [
    {
      "id": "jvm-gc",
      "title": "GC 垃圾回收",
      "summary": "JVM 垃圾回收的三种核心算法及常用收集器",
      "parentId": "jvm-memory",
      "tags": ["JVM", "GC"],
      "importance": 5,
      "source": "面渣逆袭 JVM.pdf"
    }
  ],
  "edges": [
    {
      "from": "jvm-gc",
      "to": "jvm-memory",
      "type": "prerequisite",
      "description": "理解GC需要先了解内存模型"
    }
  ]
}
```

### 关系类型

| 类型 | 含义 | 图例色 |
|------|------|--------|
| `prerequisite` | 前置知识 | 蓝色 |
| `contains` | 包含关系 | 绿色 |
| `related` | 相关概念 | 紫色 |
| `compare` | 对比关系 | 红色 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 文档解析 | PyMuPDF, python-docx |
| AI 提取 | MiniMax M2.7 API |
| 思维导图 | Markmap (D3.js) |
| 知识图谱 | Vis.js Network |
| 部署 | GitHub Pages |
