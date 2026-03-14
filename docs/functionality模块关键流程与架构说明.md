# `examples/functionality` 模块关键流程与架构说明

本文档用于快速理解 `examples/functionality` 中各能力模块的定位、核心概念、关键流程与整体架构关系，并提供 Mermaid 图辅助说明。

---

## 1. 模块总览

`examples/functionality` 主要覆盖以下能力域：

- **代理编排能力**：`plan`、`agent_skill`、`stream_printing_messages`
- **知识增强能力**：`rag`、`vector_store`
- **工具与协议能力**：`mcp`
- **记忆与状态能力**：`short_term_memory`、`long_term_memory`、`session_with_sqlite`
- **输出形态能力**：`structured_output`、`tts`

典型入口文件示例：

- `examples/functionality/rag/basic_usage.py`
- `examples/functionality/mcp/main.py`
- `examples/functionality/plan/main_agent_managed_plan.py`
- `examples/functionality/short_term_memory/memory_compression/main.py`
- `examples/functionality/long_term_memory/reme/tool_memory_example.py`
- `examples/functionality/structured_output/main.py`
- `examples/functionality/tts/main.py`

---

## 2. 核心概念

- **ReActAgent**：大多数示例的执行中枢，负责“推理 + 工具调用 + 回答生成”。
- **Toolkit/Tools**：将本地或远端能力注册为可调用工具（如 `mcp`、`agent_skill`、memory tools）。
- **Memory 分层**：
  - 短期记忆：会话上下文维持与压缩（如 `MemoryWithCompress`、ReMe 短期记忆）。
  - 长期记忆：跨会话持久化经验与用户偏好（Personal/Task/Tool Memory）。
  - 会话持久化：通过 SQLite 等后端保存/恢复 session。
- **RAG 增强**：通过检索结果扩充提示词上下文，提升知识问答准确性。
- **Structured Output**：通过 Pydantic Schema 约束输出结构，保证可解析和类型安全。
- **Streaming/TTS**：支持增量消息输出与语音播报，优化交互体验。

---

## 3. 整体架构图（功能分层）

```mermaid
flowchart LR
    %% 样式定义（参考项目 Mermaid 风格）
    classDef producerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef topicStyle fill:#ffd700,stroke:#333,stroke-width:3px
    classDef partitionStyle1 fill:#9ff,stroke:#333,stroke-width:2px
    classDef partitionStyle2 fill:#9f9,stroke:#333,stroke-width:2px
    classDef consumerGroup1Style fill:#ff9,stroke:#333,stroke-width:2px
    classDef consumerGroup2Style fill:#f99,stroke:#333,stroke-width:2px
    classDef subgraphStyle fill:#f5f5f5,stroke:#666,stroke-width:1px,rounded:10px
    classDef kafkaClusterStyle fill:#e8f4f8,stroke:#4299e1,stroke-width:1.5px,rounded:10px
    classDef ruleNoteStyle fill:#fff8e6,stroke:#ffb74d,stroke-width:1px,rounded:8px

    subgraph interactionLayer["交互层"]
        U[用户输入]:::producerStyle
        ST[流式输出<br/>stream_printing_messages]:::consumerGroup1Style
        TTS[TTS 语音输出<br/>tts]:::consumerGroup2Style
    end
    class interactionLayer subgraphStyle

    subgraph coreLayer["Agent 编排核心层"]
        RA[ReActAgent]:::topicStyle
        PL[计划管理<br/>plan]:::partitionStyle1
        SK[技能注入<br/>agent_skill]:::partitionStyle2
        SO[结构化输出<br/>structured_output]:::partitionStyle2
    end
    class coreLayer kafkaClusterStyle

    subgraph capabilityLayer["能力扩展层"]
        RAG[RAG 检索增强<br/>rag]:::consumerGroup1Style
        MCP[MCP 工具协议<br/>mcp]:::consumerGroup2Style
    end
    class capabilityLayer subgraphStyle

    subgraph memoryLayer["记忆与状态层"]
        STM[短期记忆<br/>short_term_memory]:::partitionStyle1
        LTM[长期记忆<br/>long_term_memory]:::partitionStyle2
        SDB[会话持久化<br/>session_with_sqlite]:::partitionStyle2
        VS[向量存储<br/>vector_store]:::partitionStyle1
    end
    class memoryLayer subgraphStyle

    U -->|请求| RA
    RA -->|规划/分解| PL
    RA -->|调用技能| SK
    RA -->|约束输出| SO
    RA -->|检索知识| RAG
    RA -->|调用外部工具| MCP
    RA -->|读写上下文| STM
    RA -->|沉淀经验| LTM
    RA -->|保存会话| SDB
    RAG -->|向量检索| VS
    RA -->|文本回复| ST
    ST -->|可选语音播报| TTS

    linkStyle 0,1,2,3 stroke:#666,stroke-width:1.5px,arrowheadStyle:filled
    linkStyle 4,5,6,7,8 stroke:#333,stroke-width:2px,arrowheadStyle:filled
    linkStyle 9,10,11 stroke:#4299e1,stroke-width:1.5px,arrowheadStyle:filled

    Note[关键原则：<br/>1. ReActAgent 作为统一编排入口<br/>2. Memory/RAG/MCP 作为可组合能力插件<br/>3. 输出可在文本、结构化、语音三种形态间切换]:::ruleNoteStyle
    Note -.-> coreLayer
```

---

## 4. 关键流程一：统一请求处理主流程

```mermaid
flowchart TD
    classDef producerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef topicStyle fill:#ffd700,stroke:#333,stroke-width:3px
    classDef partitionStyle1 fill:#9ff,stroke:#333,stroke-width:2px
    classDef partitionStyle2 fill:#9f9,stroke:#333,stroke-width:2px
    classDef consumerGroup1Style fill:#ff9,stroke:#333,stroke-width:2px
    classDef consumerGroup2Style fill:#f99,stroke:#333,stroke-width:2px
    classDef ruleNoteStyle fill:#fff8e6,stroke:#ffb74d,stroke-width:1px,rounded:8px

    A[收到用户请求]:::producerStyle --> B[ReActAgent 意图解析]:::topicStyle
    B --> C{是否需要规划?}:::partitionStyle1
    C -->|是| D[创建/更新 Plan]:::partitionStyle2
    C -->|否| E[直接执行当前步骤]:::partitionStyle2
    D --> E
    E --> F{是否需要外部能力?}:::partitionStyle1

    F -->|知识检索| G[RAG 检索并注入上下文]:::consumerGroup1Style
    F -->|工具执行| H[MCP/本地工具调用]:::consumerGroup2Style
    F -->|无| I[仅模型推理]:::partitionStyle2

    G --> J[汇总中间结果]:::topicStyle
    H --> J
    I --> J

    J --> K{是否要求结构化输出?}:::partitionStyle1
    K -->|是| L[Pydantic 校验并返回 JSON]:::consumerGroup1Style
    K -->|否| M[返回自然语言文本]:::consumerGroup2Style

    L --> N[可选: 流式打印/TTS]:::producerStyle
    M --> N

    Note[流程要点：<br/>1. 规划、检索、工具调用是可选分支<br/>2. 结构化输出发生在最终回答阶段<br/>3. 流式与语音是展示层增强，不改变核心推理链路]:::ruleNoteStyle
    Note -.-> J
```

---

## 5. 关键流程二：记忆系统协同流程

```mermaid
flowchart LR
    classDef producerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef topicStyle fill:#ffd700,stroke:#333,stroke-width:3px
    classDef partitionStyle1 fill:#9ff,stroke:#333,stroke-width:2px
    classDef partitionStyle2 fill:#9f9,stroke:#333,stroke-width:2px
    classDef consumerGroup1Style fill:#ff9,stroke:#333,stroke-width:2px
    classDef consumerGroup2Style fill:#f99,stroke:#333,stroke-width:2px
    classDef subgraphStyle fill:#f5f5f5,stroke:#666,stroke-width:1px,rounded:10px
    classDef ruleNoteStyle fill:#fff8e6,stroke:#ffb74d,stroke-width:1px,rounded:8px

    subgraph runtime["运行期上下文"]
        U[新消息]:::producerStyle
        STM[短期记忆缓存]:::partitionStyle1
        CMP[超阈值压缩<br/>memory_compression]:::partitionStyle2
    end
    class runtime subgraphStyle

    subgraph persistence["持久化记忆"]
        PM[Personal Memory]:::consumerGroup1Style
        TM[Task Memory]:::consumerGroup1Style
        TLM[Tool Memory]:::consumerGroup2Style
        SQL[Session SQLite]:::consumerGroup2Style
    end
    class persistence subgraphStyle

    AG[ReActAgent]:::topicStyle -->|写入对话| STM
    U --> AG
    STM -->|触发压缩条件| CMP
    CMP -->|压缩摘要回填| STM

    AG -->|跨会话沉淀| PM
    AG -->|轨迹学习| TM
    AG -->|工具经验沉淀| TLM
    AG -->|保存/恢复 session| SQL

    PM -->|语义检索召回| AG
    TM -->|相似任务经验| AG
    TLM -->|工具使用指南| AG
    SQL -->|恢复历史上下文| AG

    Note[记忆分工：<br/>1. 短期记忆保证当前会话连贯性<br/>2. 长期记忆负责跨会话知识沉淀<br/>3. Session 持久化负责状态恢复与续聊]:::ruleNoteStyle
    Note -.-> persistence
```

---

## 6. 各子模块与关键流程映射

| 子模块 | 关键概念 | 核心流程关键词 | 典型入口 |
|---|---|---|---|
| `rag` | 检索增强生成 | 查询 -> 检索 -> 上下文拼接 -> 生成 | `basic_usage.py` / `react_agent_integration.py` |
| `mcp` | 统一工具协议 | 启动 MCP Server -> 注册工具 -> Agent 调用 | `main.py` |
| `plan` | 显式任务规划 | 生成计划 -> 分步执行 -> 进度更新 | `main_manual_plan.py` / `main_agent_managed_plan.py` |
| `structured_output` | Schema 约束输出 | 传入 `structured_model` -> 校验 -> JSON 输出 | `main.py` |
| `short_term_memory` | 上下文压缩 | token 统计 -> 触发压缩 -> 摘要回填 | `memory_compression/main.py` |
| `long_term_memory` | 跨会话记忆 | 记录经验 -> 向量检索 -> 注入推理 | `reme/*.py` / `mem0/memory_example.py` |
| `session_with_sqlite` | 会话持久化 | 保存 session -> 载入 session -> 续聊 | `main.py` |
| `stream_printing_messages` | 流式可观测性 | chunk 输出 -> 按消息 ID 聚合展示 | `single_agent.py` / `multi_agent.py` |
| `tts` | 语音反馈 | 文本回复 -> TTS 合成 -> 实时播报 | `main.py` |
| `agent_skill` | 领域技能增强 | 注册 Skill -> 按需调用 -> 回传结果 | `main.py` |
| `vector_store` | 检索基础设施 | 向量化 -> 索引存储 -> 相似度召回 | `*/main.py` |

---

## 7. 推荐阅读顺序

为快速上手，建议按以下路径阅读与运行：

1. `structured_output`（最容易验证输出质量）
2. `plan` + `mcp`（理解编排与工具调用）
3. `rag` + `vector_store`（理解知识增强链路）
4. `short_term_memory` + `long_term_memory` + `session_with_sqlite`（理解状态与记忆体系）
5. `stream_printing_messages` + `tts`（补齐交互体验层）

