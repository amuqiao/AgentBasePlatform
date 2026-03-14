# `examples/workflows` 模块关键流程与架构说明

本文档面向 `examples/workflows`，用于说明该模块的核心概念、关键流程与系统架构，并提供 Mermaid 图辅助理解。

---

## 1. 快速阅读（合并自 README 精简版）

`examples/workflows` 通过四类示例展示 AgentScope 的工作流编排能力：

- `multiagent_concurrent`：并发执行与聚合结果（`asyncio.gather` / `fanout_pipeline`）
- `multiagent_conversation`：多角色共享会话空间（`MsgHub` + 顺序发言）
- `multiagent_debate`：带裁判的多轮辩论闭环（结构化判断是否结束）
- `multiagent_realtime`：实时语音多智能体会话（`ChatRoom` + WebSocket）

这些示例覆盖了从“离线任务并发”到“在线实时交互”的典型多智能体工作流形态。

---

## 2. 模块定位与能力边界

`examples/workflows` 的核心目标是演示“工作流编排”而非具体业务领域逻辑，重点能力包括：

- **执行编排**：顺序、并发、广播、循环终止条件
- **上下文共享**：在受控范围内共享对话消息与状态
- **角色协作**：多 Agent 分工（参与者、辩手、裁判、实时语音角色）
- **结构化控制**：通过结构化输出驱动流程分支与停止条件
- **实时连接**：WebSocket 驱动前后端实时事件流与音频流

---

## 3. 核心概念

- **Agent（`ReActAgent` / `RealtimeAgent` / `AgentBase`）**：执行单元，负责生成响应、消费上下文、输出结果。
- **Msg / MsgHub**：消息载体与共享会话空间；`MsgHub` 决定谁能看到哪些消息，并支持广播。
- **Pipeline**：
  - `sequential_pipeline`：按顺序执行，适合轮流发言；
  - `fanout_pipeline`：并发分发并收集结果，适合投票、并行求解。
- **Structured Output（Pydantic）**：将 LLM 输出约束为结构化字段，用于自动判定流程状态（如 `finished`）。
- **ChatRoom（Realtime）**：管理多个实时 Agent 的生命周期与消息转发。
- **ClientEvents / ServerEvents**：前后端在 WebSocket 上交换的协议事件。

---

## 4. 系统架构总览

```mermaid
flowchart LR
    %% 样式定义（对齐参考风格）
    classDef producerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef topicStyle fill:#ffd700,stroke:#333,stroke-width:3px
    classDef partitionStyle1 fill:#9ff,stroke:#333,stroke-width:2px
    classDef partitionStyle2 fill:#9f9,stroke:#333,stroke-width:2px
    classDef consumerGroup1Style fill:#ff9,stroke:#333,stroke-width:2px
    classDef consumerGroup2Style fill:#f99,stroke:#333,stroke-width:2px
    classDef subgraphStyle fill:#f5f5f5,stroke:#666,stroke-width:1px,rounded:10px
    classDef kafkaClusterStyle fill:#e8f4f8,stroke:#4299e1,stroke-width:1.5px,rounded:10px
    classDef ruleNoteStyle fill:#fff8e6,stroke:#ffb74d,stroke-width:1px,rounded:8px

    subgraph appLayer["示例入口层"]
        CONCURRENT[`multiagent_concurrent/main.py`]:::producerStyle
        CONVERSATION[`multiagent_conversation/main.py`]:::producerStyle
        DEBATE[`multiagent_debate/main.py`]:::producerStyle
        REALTIME[`multiagent_realtime/run_server.py`]:::producerStyle
    end
    class appLayer subgraphStyle

    subgraph orchestrateLayer["编排与路由层"]
        PIPE[Pipeline<br/>sequential/fanout]:::topicStyle
        HUB[MsgHub<br/>共享会话与广播]:::partitionStyle1
        ROOM[ChatRoom<br/>实时多Agent会话]:::partitionStyle2
    end
    class orchestrateLayer kafkaClusterStyle

    subgraph runtimeLayer["Agent 与模型运行层"]
        AGENT[ReActAgent / RealtimeAgent / AgentBase]:::consumerGroup1Style
        MODEL[DashScope / Gemini / OpenAI Realtime]:::consumerGroup2Style
    end
    class runtimeLayer subgraphStyle

    subgraph protocolLayer["协议与控制层"]
        MSG[Msg / TextBlock]:::partitionStyle1
        SCHEMA[Pydantic Structured Output]:::partitionStyle2
        EVENT[ClientEvents / ServerEvents]:::consumerGroup1Style
    end
    class protocolLayer subgraphStyle

    subgraph ioLayer["接口与展示层"]
        WS[WebSocket API]:::consumerGroup2Style
        UI[multi_agent.html]:::topicStyle
    end
    class ioLayer subgraphStyle

    CONCURRENT -->|并发任务| PIPE
    CONVERSATION -->|轮流发言| PIPE
    CONVERSATION -->|共享上下文| HUB
    DEBATE -->|辩手消息共享| HUB
    DEBATE -->|终止判定| SCHEMA
    REALTIME -->|创建会话| ROOM
    ROOM --> AGENT
    AGENT --> MODEL
    PIPE --> AGENT
    HUB --> MSG
    REALTIME --> EVENT
    EVENT --> WS
    UI -->|发送事件| WS
    WS -->|回传事件/音频| UI

    linkStyle 0,1,2,3 stroke:#666,stroke-width:1.5px,arrowheadStyle:filled
    linkStyle 4,5,6,7,8 stroke:#333,stroke-width:2px,arrowheadStyle:filled
    linkStyle 9,10,11,12,13 stroke:#4299e1,stroke-width:1.5px,arrowheadStyle:filled

    Note[架构要点：<br/>1. Pipeline/MsgHub/ChatRoom 是三类编排核心<br/>2. Structured Output 用于控制流程闭环<br/>3. 实时场景通过 WebSocket 承载事件与媒体流]:::ruleNoteStyle
    Note -.-> orchestrateLayer
```

---

## 5. 关键流程 A：并发执行与结果聚合（`multiagent_concurrent`）

该示例演示两种并发模式：

- `asyncio.gather`：直接并发执行多个 Agent 调用。
- `fanout_pipeline(enable_gather=True)`：统一分发输入并收集输出，便于后续统计。

```mermaid
flowchart TD
    classDef producerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef topicStyle fill:#ffd700,stroke:#333,stroke-width:3px
    classDef partitionStyle1 fill:#9ff,stroke:#333,stroke-width:2px
    classDef partitionStyle2 fill:#9f9,stroke:#333,stroke-width:2px
    classDef consumerGroup1Style fill:#ff9,stroke:#333,stroke-width:2px
    classDef consumerGroup2Style fill:#f99,stroke:#333,stroke-width:2px
    classDef ruleNoteStyle fill:#fff8e6,stroke:#ffb74d,stroke-width:1px,rounded:8px

    A[创建 Alice/Bob/Chalice]:::producerStyle --> B{并发模式选择}:::partitionStyle1
    B -->|方式1| C[asyncio.gather 并发调用]:::topicStyle
    B -->|方式2| D[fanout_pipeline 并发分发]:::partitionStyle2
    C --> E[每个 Agent 记录耗时并返回 Msg.metadata.time]:::consumerGroup1Style
    D --> E
    E --> F[聚合各 Agent 耗时]:::consumerGroup2Style
    F --> G[计算平均耗时并输出]:::topicStyle

    Note[关键点：<br/>1. gather 偏“原生并发”<br/>2. fanout 偏“工作流语义化并发+收集”]:::ruleNoteStyle
    Note -.-> B
```

---

## 6. 关键流程 B：共享会话与广播（`multiagent_conversation`）

该示例展示如何在一个共享会话空间中组织多参与者对话，并支持成员动态变更。

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

    START[创建三位 ReActAgent]:::producerStyle --> HUBINIT[进入 MsgHub<br/>附带系统公告]:::topicStyle

    subgraph round["会话轮次"]
        S1[sequential_pipeline: Alice]:::consumerGroup1Style --> S2[Bob]:::consumerGroup1Style --> S3[Charlie]:::consumerGroup1Style
    end
    class round subgraphStyle

    HUBINIT --> round
    S3 --> DEL[删除 Bob 参与者]:::partitionStyle1
    DEL --> BC[伪造 Bob 离场广播]:::partitionStyle2
    BC --> NEXT[Alice 与 Charlie 继续对话]:::consumerGroup2Style

    Note[关键点：<br/>1. MsgHub 决定消息共享边界<br/>2. 支持运行期增删成员与广播事件]:::ruleNoteStyle
    Note -.-> HUBINIT
```

---

## 7. 关键流程 C：多轮辩论与裁判闭环（`multiagent_debate`）

该示例体现“讨论-裁判-继续/结束”的循环式工作流。

```mermaid
flowchart TD
    classDef producerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef topicStyle fill:#ffd700,stroke:#333,stroke-width:3px
    classDef partitionStyle1 fill:#9ff,stroke:#333,stroke-width:2px
    classDef partitionStyle2 fill:#9f9,stroke:#333,stroke-width:2px
    classDef consumerGroup1Style fill:#ff9,stroke:#333,stroke-width:2px
    classDef consumerGroup2Style fill:#f99,stroke:#333,stroke-width:2px
    classDef ruleNoteStyle fill:#fff8e6,stroke:#ffb74d,stroke-width:1px,rounded:8px

    A[初始化 Alice/Bob/Aggregator]:::producerStyle --> B[进入 while 循环]:::topicStyle
    B --> C[MsgHub 内：Alice 正方发言]:::consumerGroup1Style
    C --> D[MsgHub 内：Bob 反方发言]:::consumerGroup1Style
    D --> E[退出 MsgHub]:::partitionStyle1
    E --> F[单独调用 Aggregator 裁判]:::partitionStyle2
    F --> G[按 JudgeModel 解析 structured output]:::consumerGroup2Style
    G --> H{finished == true ?}:::partitionStyle1
    H -->|否| B
    H -->|是| I[输出 correct_answer 并结束]:::topicStyle

    Note[关键点：<br/>1. 辩手共享上下文，裁判独立决策<br/>2. 结构化字段 finished 决定循环终止]:::ruleNoteStyle
    Note -.-> G
```

---

## 8. 关键流程 D：实时语音会话（`multiagent_realtime`）

该示例提供前后端协同的实时工作流：前端发事件、后端建会话、ChatRoom 驱动双 Agent 自主对话并回传事件。

```mermaid
sequenceDiagram
    participant UI as 前端页面
    participant WS as WebSocket端点
    participant SRV as run_server.py
    participant ROOM as ChatRoom
    participant A1 as RealtimeAgent1
    participant A2 as RealtimeAgent2

    UI->>WS: 连接 /ws/{user_id}/{session_id}
    UI->>WS: client_session_create(名称/指令/模型提供商)
    WS->>SRV: 解析 ClientEvents
    SRV->>SRV: 创建 RealtimeModel + Agent1/Agent2
    SRV->>ROOM: ChatRoom(agents=[A1,A2]) + start(queue)
    SRV-->>UI: server_session_created
    SRV->>A1: 注入 "<system>Now you can talk.</system>"

    loop 实时对话
        ROOM->>A1: 转发输入事件
        A1-->>ROOM: 文本/音频事件
        ROOM->>A2: 广播消息
        A2-->>ROOM: 文本/音频事件
        ROOM-->>UI: ServerEvents(JSON)
    end

    UI->>WS: client_session_end
    WS->>ROOM: stop()
    ROOM-->>UI: 会话结束状态
```

---

## 9. 关键文件职责映射

| 文件 | 职责 | 关键点 |
|---|---|---|
| `examples/workflows/multiagent_concurrent/main.py` | 并发执行示例 | 对比 `asyncio.gather` 与 `fanout_pipeline`，并统计耗时 |
| `examples/workflows/multiagent_conversation/main.py` | 多人共享会话示例 | `MsgHub` 广播、`sequential_pipeline` 轮流发言、动态删成员 |
| `examples/workflows/multiagent_debate/main.py` | 辩论闭环示例 | 两辩手 + 裁判，`JudgeModel` 结构化判定循环结束 |
| `examples/workflows/multiagent_realtime/run_server.py` | 实时语音服务端 | FastAPI + WebSocket，创建 `ChatRoom` 与实时 Agent |
| `examples/workflows/multiagent_realtime/multi_agent.html` | 实时前端界面 | 发起会话、接收事件、播放音频、展示 transcript |
| `examples/workflows/*/README.md` | 示例使用说明 | 启动方式、模型配置与扩展建议 |

---

## 10. 实践建议（从示例走向生产）

- **统一工作流抽象**：将“并发-广播-裁判-终止”提炼为可复用流程模板。
- **增强可观测性**：记录每轮输入、输出、耗时、结构化判定结果，支持回放与排障。
- **失败与重试策略**：为模型调用、WebSocket 中断、事件解析异常添加降级与恢复机制。
- **状态外置化**：将会话状态与关键决策持久化，支撑长对话与多实例部署。
- **安全与配额治理**：对 API Key、并发连接数、模型调用频次进行统一治理。

