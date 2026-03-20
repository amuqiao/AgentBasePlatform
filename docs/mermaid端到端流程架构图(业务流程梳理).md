## 端到端流程 mermaid 作图风格参考

> 在业务流程梳理中使用 Mermaid 图表时，可参考以下风格规范。
> 这是一份风格参考而非硬性要求，根据流程复杂度灵活取舍。

## 端到端流程架构图示例
> 展示用户输入 → 预处理 → 记忆检索 → 上下文构建 → LLM 推理 → 后处理 → 持久化的完整 AI 对话记忆流程

```mermaid
flowchart LR
    %% ── 配色定义：按流程阶段职责分色 ──────────────────────────────
    classDef userStyle     fill:#1e40af,stroke:#1e3a8a,stroke-width:2.5px,color:#fff
    classDef routeStyle    fill:#4f46e5,stroke:#3730a3,stroke-width:2px,color:#fff
    classDef retrieveStyle fill:#d97706,stroke:#92400e,stroke-width:2px,color:#fff
    classDef llmStyle      fill:#dc2626,stroke:#991b1b,stroke-width:2.5px,color:#fff
    classDef storeStyle    fill:#059669,stroke:#064e3b,stroke-width:2px,color:#fff
    classDef dbStyle       fill:#374151,stroke:#111827,stroke-width:2px,color:#fff
    classDef noteStyle     fill:#fffbeb,stroke:#f59e0b,stroke-width:1.5px,color:#78350f
    classDef layerStyle    fill:#f8fafc,stroke:#cbd5e0,stroke-width:1.5px

    %% ── 起始节点 ────────────────────────────────────────────────
    USER["用户输入<br>User Input"]:::userStyle

    %% ── 预处理层 ─────────────────────────────────────────────────
    subgraph Preprocessing["预处理层"]
        direction LR
        PP1["意图识别<br>Intent Classification"]:::routeStyle
        PP2["实体提取<br>NER Extraction"]:::routeStyle
        PP3["记忆信号检测<br>Memory Signal Detection"]:::routeStyle
    end
    class Preprocessing layerStyle

    %% ── 记忆检索层 ───────────────────────────────────────────────
    subgraph MemoryRetrieval["记忆检索层"]
        direction LR
        MR1["语义检索<br>Semantic Search"]:::retrieveStyle
        MR2["结构化查询<br>Structured Query"]:::retrieveStyle
        MR3["结果融合排序<br>RRF Fusion"]:::retrieveStyle
    end
    class MemoryRetrieval layerStyle

    %% ── 上下文构建层 ─────────────────────────────────────────────
    subgraph ContextBuild["上下文构建层"]
        direction LR
        CB1["System Prompt<br>角色与规则"]:::routeStyle
        CB2["记忆注入<br>Memory Injection"]:::retrieveStyle
        CB3["当前对话<br>Current Dialog"]:::userStyle
    end
    class ContextBuild layerStyle

    %% ── 核心推理节点 ─────────────────────────────────────────────
    LLM["大语言模型推理<br>LLM Inference"]:::llmStyle

    %% ── 后处理层 ─────────────────────────────────────────────────
    subgraph PostProcess["后处理层"]
        direction LR
        POST1["回复质量检查<br>Quality Check"]:::routeStyle
        POST2["新记忆提取<br>Memory Extraction"]:::storeStyle
        POST3["记忆价值评估<br>Value Assessment"]:::storeStyle
    end
    class PostProcess layerStyle

    %% ── 持久化层 ─────────────────────────────────────────────────
    subgraph Storage["持久化层"]
        direction LR
        DB1[("向量数据库<br>Vector DB")]:::dbStyle
        DB2[("用户画像文件<br>Profile JSON")]:::dbStyle
        DB3[("情景日志<br>Episode Log")]:::dbStyle
    end
    class Storage layerStyle

    %% ── 终止节点 ────────────────────────────────────────────────
    RESPONSE["输出回复<br>Response"]:::userStyle

    %% ── 主流程数据流 ─────────────────────────────────────────────
    USER --> Preprocessing
    Preprocessing --> MemoryRetrieval
    Preprocessing --> CB3
    MemoryRetrieval --> CB2
    CB1 --> LLM
    CB2 --> LLM
    CB3 --> LLM
    LLM --> PostProcess
    LLM --> RESPONSE
    PostProcess -->|"高价值记忆"| DB1
    PostProcess -->|"结构化信息"| DB2
    PostProcess -->|"情景摘要"| DB3
    DB1 --> MR1
    DB2 --> MR2

    %% ── 设计注记 ─────────────────────────────────────────────────
    NOTE["完整流程关键路径<br>① 检索延迟目标：< 50ms<br>② 存储操作：异步执行<br>③ 上下文记忆占比：< 30%<br>④ 每用户记忆上限：建议 10K 条"]:::noteStyle
    NOTE -.- LLM

    %% 边索引：0-13，共 14 条
    linkStyle 0 stroke:#1e40af,stroke-width:2px
    linkStyle 1 stroke:#4f46e5,stroke-width:2px
    linkStyle 2 stroke:#1e40af,stroke-width:1.5px
    linkStyle 3 stroke:#d97706,stroke-width:2px
    linkStyle 4 stroke:#dc2626,stroke-width:2px
    linkStyle 5 stroke:#dc2626,stroke-width:2px
    linkStyle 6 stroke:#dc2626,stroke-width:2px
    linkStyle 7 stroke:#4f46e5,stroke-width:2px
    linkStyle 8 stroke:#dc2626,stroke-width:2.5px
    linkStyle 9 stroke:#059669,stroke-width:2px
    linkStyle 10 stroke:#059669,stroke-width:2px
    linkStyle 11 stroke:#059669,stroke-width:2px
    linkStyle 12 stroke:#374151,stroke-width:1.5px,stroke-dasharray:4 3
    linkStyle 13 stroke:#374151,stroke-width:1.5px,stroke-dasharray:4 3
```

---

## 最佳实践速查

| 设计原则 | 说明 |
|----------|------|
| **配色与样式定义** | 通过 `classDef` 预定义各阶段节点的颜色和边框样式，按业务职责区分：输入/输出用深蓝（`#1e40af`），处理/路由用靛蓝（`#4f46e5`），检索用琥珀（`#d97706`），核心推理用红色（`#dc2626`），存储写入用绿色（`#059669`），数据库用深灰（`#374151`）；注记节点用低饱和暖色（`#fffbeb`） |
| **流程方向选择** | 线性主流程用 `LR`（从左到右），强调分层纵向关系时用 `TB`；子图内使用 `direction LR` 保持内部水平排列，增强可读性 |
| **分层 subgraph** | 使用 `subgraph` 将同阶段节点归组，体现流程的阶段划分；每个子图对应一个处理职责（如预处理、检索、推理等）；`class SubgraphName layerStyle` 统一背景色区分层级 |
| **起止节点突出** | 流程的起始节点（用户输入）和终止节点（输出回复）使用最高对比度颜色（`#1e40af`深蓝），与中间处理节点形成视觉区分，一眼识别流程边界 |
| **连接线区分** | `-->` 表示主流程同步调用；`-.->` 表示异步调用或可选路径；`==>` 表示关键/强制路径；连接线标签简明描述数据内容或操作语义（如 `"高价值记忆"`、`"结构化信息"`） |
| **`linkStyle` 索引精准计数** | `linkStyle N` 按边的**声明顺序**从 0 开始编号，索引越界会触发渲染崩溃。两条规避守则：① **展开 `&`**：`A & B --> C` 会展开为多条独立边，凡使用 `linkStyle` 的图一律拆成独立行 `A --> C` / `B --> C`；② **注释标注边总数**：在连接线声明结束后、`linkStyle` 之前插入 `%% 边索引：0-N，共 X 条` 注释强制核对 |
| **节点形状语义** | `["text"]` 矩形表示处理节点/服务；`[("text")]` 圆柱体表示持久化存储（DB、向量库、文件等）；形状与颜色双重编码，直观区分计算与存储职责 |
| **节点换行** | 节点文本内换行须使用 `<br>` 标签（如 `["组件名<br>副标题"]`）；首行写中文业务名，`<br>` 后补英文技术名，兼顾业务可读性与技术精确性 |
| **辅助 NOTE 注记** | 对关键路径的性能指标、约束条件或设计决策，通过 `NOTE` 节点附加说明；使用 `NOTE -.- 核心节点` 悬浮注记模式，与主流程连接线视觉隔离，避免干扰 |
| **中英双语** | 节点文本和连接线标签适当中英双语（如 `"语义检索<br>Semantic Search"`），兼顾业务可读性与技术国际化 |
