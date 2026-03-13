# AgentScope Studio 集成详细设计文档

> **版本**：v1.0 | **日期**：2026-03-13 | **定位**：AgentScope Studio 与智能体平台集成技术方案

---

## 一、文档说明

### 1.1 设计目标

本文档基于《智能体平台架构设计文档》中关于 AgentScope Studio 的定位，详细阐述 Studio 与平台各层（前端展示层、应用服务层、智能体运行层）的具体集成方案。

### 1.2 集成范围

| 集成维度 | 说明 |
|----------|------|
| **前端集成** | Studio 可视化界面如何嵌入/复用到平台管理控制台 |
| **API 对接** | Studio 与后端服务的接口定义与数据交互 |
| **数据流** | 消息流追踪、调试数据同步机制 |
| **权限集成** | Studio 功能如何与平台 RBAC/ABAC 权限体系打通 |
| **部署方式** | Studio 独立部署 vs 内嵌部署的技术方案 |

---

## 二、AgentScope Studio 生态定位回顾

### 2.1 Studio 核心能力

根据 [AgentScope 生态圈](./agentscope生态圈.md) 定义，Studio 是**可视化开发/调试平台**：

| 能力 | 描述 |
|------|------|
| 图形化配置 | 可视化配置智能体、定义协作逻辑 |
| 实时调试 | 实时调试多智能体交互过程 |
| 消息流监控 | 可视化监控消息流转/日志 |

### 2.2 Studio 技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 前端框架 | React + TypeScript | 与平台前端技术栈一致 |
| UI 体系 | AgentScope Spark Design | 统一设计规范 |
| 后端服务 | Python (FastAPI/Flask) | 提供调试数据 API |
| 通信协议 | WebSocket / HTTP SSE | 实时消息流推送 |

---

## 三、整体集成架构

### 3.1 集成架构全景图

```mermaid
flowchart TB
    %% 样式定义
    classDef platformStyle fill:#4299e1,stroke:#2b6cb0,stroke-width:2px,color:#fff
    classDef studioStyle fill:#9f7aea,stroke:#553c9a,stroke-width:2px,color:#fff
    classDef apiStyle fill:#38b2ac,stroke:#2c7a7b,stroke-width:2px,color:#fff
    classDef dataStyle fill:#ed8936,stroke:#c05621,stroke-width:2px,color:#fff
    classDef subgraphStyle fill:#f7fafc,stroke:#cbd5e0,stroke-width:1.5px

    %% 平台前端层
    subgraph platformFront["智能体平台前端 (React + Vite)"]
        PF1[管理控制台]:::platformStyle
        PF2[智能体编排界面]:::platformStyle
        PF3[聊天交互界面]:::platformStyle
        PF4[监控面板]:::platformStyle
    end
    class platformFront subgraphStyle

    %% Studio 前端层
    subgraph studioFront["AgentScope Studio 前端"]
        SF1[可视化编排器<br/>ReactFlow]:::studioStyle
        SF2[消息流追踪器]:::studioStyle
        SF3[调试控制台]:::studioStyle
        SF4[Agent 配置面板]:::studioStyle
    end
    class studioFront subgraphStyle

    %% 集成层
    subgraph integrationLayer["集成适配层"]
        I1[Studio Embed SDK<br/>iframe/微前端]:::apiStyle
        I2[组件复用层<br/>Spark Design]:::apiStyle
        I3[事件总线<br/>跨窗口通信]:::apiStyle
    end
    class integrationLayer subgraphStyle

    %% 平台后端层
    subgraph platformBack["智能体平台后端 (FastAPI)"]
        PB1[业务编排服务]:::platformStyle
        PB2[权限服务<br/>RBAC/ABAC]:::platformStyle
        PB3[租户中心]:::platformStyle
        PB4[Session Manager]:::platformStyle
    end
    class platformBack subgraphStyle

    %% Studio 后端层
    subgraph studioBack["AgentScope Studio 后端"]
        SB1[调试数据服务]:::studioStyle
        SB2[消息流采集器]:::studioStyle
        SB3[配置转换器]:::studioStyle
    end
    class studioBack subgraphStyle

    %% 运行层
    subgraph runtimeLayer["智能体运行层"]
        R1[Agent Manager]:::dataStyle
        R2[Message Bus]:::dataStyle
        R3[Workflow Orchestrator]:::dataStyle
    end
    class runtimeLayer subgraphStyle

    %% 连接关系
    PF1 -->|嵌入| I1
    PF2 -->|复用组件| I2
    SF1 & SF2 & SF3 & SF4 -->|注册到| I2
    I1 <-->|postMessage| I3
    
    SF1 & SF2 & SF3 & SF4 -->|API 调用| SB1 & SB2 & SB3
    SB1 & SB2 & SB3 <-->|调试数据同步| PB4
    PB1 <-->|业务数据| PF1 & PF2 & PF3 & PF4
    
    SB2 <-->|订阅消息| R2
    SB3 <-->|配置下发| R1 & R3
    
    PB2 <-->|权限校验| SB1
    PB3 <-->|租户上下文| SB1

    linkStyle 0,1,2,3 stroke:#2b6cb0,stroke-width:2px
    linkStyle 4,5,6,7 stroke:#553c9a,stroke-width:1.5px
    linkStyle 8,9,10,11 stroke:#2c7a7b,stroke-width:1.5px
```

---

## 四、前端集成方案

### 4.1 集成模式选型

| 模式 | 方案 | 适用场景 | 复杂度 |
|------|------|----------|--------|
| **模式 A** | iframe 嵌入 | 快速集成、Studio 独立部署 | 低 |
| **模式 B** | 微前端 (Module Federation) | 深度集成、共享状态 | 中 |
| **模式 C** | 组件库复用 | 仅复用可视化组件 | 低 |

**推荐方案：模式 B（微前端）+ 模式 C（组件复用）组合**

### 4.2 微前端集成架构

```mermaid
flowchart LR
    classDef hostStyle fill:#4299e1,stroke:#2b6cb0,stroke-width:2px,color:#fff
    classDef remoteStyle fill:#9f7aea,stroke:#553c9a,stroke-width:2px,color:#fff
    classDef sharedStyle fill:#38b2ac,stroke:#2c7a7b,stroke-width:2px,color:#fff

    subgraph host["平台主应用 (Host)"]
        H1[React + Vite]:::hostStyle
        H2[路由管理]:::hostStyle
        H3[状态管理<br/>Zustand]:::hostStyle
        H4[权限上下文]:::hostStyle
    end

    subgraph remote["Studio 微应用 (Remote)"]
        R1[React 组件]:::remoteStyle
        R2[可视化编排器]:::remoteStyle
        R3[消息追踪器]:::remoteStyle
    end

    subgraph shared["共享依赖"]
        S1[Spark Design]:::sharedStyle
        S2[React/TS]:::sharedStyle
        S3[工具函数]:::sharedStyle
    end

    H1 -->|Module Federation| R1
    H3 -->|共享状态| R1
    H4 -->|权限注入| R1
    R1 & R2 & R3 -->|使用| S1
    H1 -->|使用| S1
```

### 4.3 组件复用清单

| Studio 组件 | 复用方式 | 平台应用位置 |
|-------------|----------|--------------|
| AgentNode（智能体节点） | npm 包引入 | 智能体编排界面 |
| MessageFlow（消息流图） | npm 包引入 | 监控面板、调试界面 |
| ConfigPanel（配置面板） | npm 包引入 | 管理控制台 |
| DebugConsole（调试台） | iframe/微前端 | 管理控制台嵌入 |

### 4.4 前端集成代码示例

```typescript
// 平台主应用配置 (vite.config.ts)
import { defineConfig } from 'vite'
import federation from '@originjs/vite-plugin-federation'

export default defineConfig({
  plugins: [
    federation({
      remotes: {
        // Studio 微应用入口
        agentscopeStudio: 'http://studio-host/assets/remoteEntry.js',
      },
      shared: ['react', 'react-dom', '@agentscope/spark-design']
    })
  ]
})

// 平台中使用 Studio 组件
import { lazy, Suspense } from 'react'

// 动态加载 Studio 组件
const StudioWorkflowEditor = lazy(() => import('agentscopeStudio/WorkflowEditor'))
const StudioMessageTracer = lazy(() => import('agentscopeStudio/MessageTracer'))

// 在编排界面中使用
function AgentOrchestrationPage() {
  return (
    <div className="orchestration-container">
      <h1>智能体编排</h1>
      <Suspense fallback={<Loading />}>
        <StudioWorkflowEditor 
          tenantId={currentTenant.id}
          agentId={selectedAgent.id}
          onSave={handleWorkflowSave}
          readonly={!hasEditPermission}
        />
      </Suspense>
    </div>
  )
}
```

---

## 五、API 对接方案

### 5.1 API 架构分层

```mermaid
flowchart TB
    classDef gatewayStyle fill:#c6f6d5,stroke:#276749,stroke-width:2px,color:#1c4532
    classDef platformStyle fill:#4299e1,stroke:#2b6cb0,stroke-width:2px,color:#fff
    classDef studioStyle fill:#9f7aea,stroke:#553c9a,stroke-width:2px,color:#fff
    classDef runtimeStyle fill:#ed8936,stroke:#c05621,stroke-width:2px,color:#fff

    subgraph gateway["API 网关层"]
        G1[统一入口<br/>鉴权/限流/路由]:::gatewayStyle
    end

    subgraph platform["平台服务层"]
        P1[业务编排 API]:::platformStyle
        P2[权限服务 API]:::platformStyle
        P3[租户中心 API]:::platformStyle
        P4[Session API]:::platformStyle
    end

    subgraph studio["Studio 服务层"]
        S1[调试数据 API]:::studioStyle
        S2[配置管理 API]:::studioStyle
        S3[消息流 API<br/>WebSocket]:::studioStyle
    end

    subgraph runtime["运行层"]
        R1[Agent Runtime]:::runtimeStyle
        R2[Message Bus]:::runtimeStyle
    end

    G1 -->|/api/v1/platform/*| P1 & P2 & P3 & P4
    G1 -->|/api/v1/studio/*| S1 & S2 & S3
    S1 & S2 -->|数据同步| P4
    S3 <-->|实时消息| R2
    S2 -->|配置下发| R1
```

### 5.2 API 接口定义

#### 5.2.1 Studio 调试数据 API

```yaml
# OpenAPI 规范片段
openapi: 3.0.0
paths:
  /api/v1/studio/debug/sessions:
    get:
      summary: 获取调试会话列表
      parameters:
        - name: tenant_id
          in: query
          required: true
          schema:
            type: string
        - name: agent_id
          in: query
          schema:
            type: string
      responses:
        200:
          description: 调试会话列表
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/DebugSession'

  /api/v1/studio/debug/sessions/{session_id}/messages:
    get:
      summary: 获取会话消息流
      parameters:
        - name: session_id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: 消息流数据
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/MessageFlow'

  /api/v1/studio/debug/sessions/{session_id}/stream:
    get:
      summary: WebSocket 实时消息流
      parameters:
        - name: session_id
          in: path
          required: true
          schema:
            type: string
      responses:
        101:
          description: WebSocket 连接升级

components:
  schemas:
    DebugSession:
      type: object
      properties:
        session_id:
          type: string
        agent_id:
          type: string
        tenant_id:
          type: string
        status:
          type: string
          enum: [running, paused, completed, error]
        created_at:
          type: string
          format: date-time
        message_count:
          type: integer

    MessageFlow:
      type: object
      properties:
        message_id:
          type: string
        session_id:
          type: string
        source_agent:
          type: string
        target_agent:
          type: string
        message_type:
          type: string
          enum: [text, tool_call, tool_result, system]
        content:
          type: object
        timestamp:
          type: string
          format: date-time
        latency_ms:
          type: integer
```

#### 5.2.2 配置管理 API

```yaml
  /api/v1/studio/agents/{agent_id}/config:
    get:
      summary: 获取 Agent 可视化配置
      responses:
        200:
          description: Agent 配置
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AgentConfig'

    post:
      summary: 保存 Agent 可视化配置
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AgentConfig'
      responses:
        200:
          description: 配置保存成功

components:
  schemas:
    AgentConfig:
      type: object
      properties:
        agent_id:
          type: string
        tenant_id:
          type: string
        workflow_definition:
          type: object
          description: DAG 工作流定义
        node_configs:
          type: array
          items:
            type: object
            properties:
              node_id:
                type: string
              node_type:
                type: string
                enum: [agent, tool, condition, parallel]
              config:
                type: object
        connections:
          type: array
          items:
            type: object
            properties:
              source:
                type: string
              target:
                type: string
              condition:
                type: string
```

---

## 六、数据流与同步机制

### 6.1 消息流追踪数据流

```mermaid
sequenceDiagram
    participant User as 用户
    participant PlatformUI as 平台前端
    participant StudioUI as Studio 前端
    participant StudioAPI as Studio API
    participant MessageBus as Message Bus
    participant Agent as Agent Runtime

    User->>PlatformUI: 打开调试面板
    PlatformUI->>StudioUI: 加载 Studio 调试组件
    StudioUI->>StudioAPI: GET /debug/sessions
    StudioAPI->>StudioUI: 返回会话列表
    
    User->>StudioUI: 选择调试会话
    StudioUI->>StudioAPI: WebSocket /debug/sessions/{id}/stream
    StudioAPI->>MessageBus: 订阅消息主题
    
    loop 消息产生
        Agent->>MessageBus: 发送消息
        MessageBus->>StudioAPI: 推送消息
        StudioAPI->>StudioUI: WebSocket 推送
        StudioUI->>StudioUI: 更新消息流图
    end
    
    User->>StudioUI: 查看消息详情
    StudioUI->>PlatformUI: postMessage 传递选中消息
    PlatformUI->>PlatformUI: 高亮关联业务数据
```

### 6.2 配置同步机制

| 同步场景 | 方向 | 机制 | 说明 |
|----------|------|------|------|
| Studio → 平台 | 配置保存 | HTTP POST + 事件通知 | Studio 保存后通知平台刷新 |
| 平台 → Studio | 配置加载 | HTTP GET + 初始化参数 | 平台传递 tenant/agent ID |
| 运行时 → Studio | 状态更新 | WebSocket 推送 | 实时同步运行状态 |

### 6.3 数据模型映射

```typescript
// Studio 配置模型 ↔ 平台运行时模型 映射
interface ConfigMapping {
  // Studio 可视化节点 → 平台 Agent 定义
  studioNodeToAgent: {
    'chat-node': 'ChatAgent'
    'tool-node': 'ToolAgent'
    'workflow-node': 'WorkflowAgent'
    'condition-node': 'ConditionRouter'
  }
  
  // Studio 连线 → 平台消息路由规则
  studioEdgeToRouting: {
    source: string      // Studio 源节点 ID
    target: string      // Studio 目标节点 ID
    condition?: string  // 条件表达式
    priority: number    // 路由优先级
  }
  
  // Studio 位置信息 → 平台仅保留布局（运行时无关）
  studioPosition: {
    x: number
    y: number
    // 仅用于可视化展示
  }
}
```

---

## 七、权限集成方案

### 7.1 权限模型对接

```mermaid
flowchart TB
    classDef rbacStyle fill:#4299e1,stroke:#2b6cb0,stroke-width:2px,color:#fff
    classDef abacStyle fill:#9f7aea,stroke:#553c9a,stroke-width:2px,color:#fff
    classDef studioStyle fill:#38b2ac,stroke:#2c7a7b,stroke-width:2px,color:#fff

    subgraph platformRBAC["平台 RBAC 体系"]
        R1[角色定义]:::rbacStyle
        R2[权限资源<br/>resource:agent, action:debug]:::rbacStyle
        R3[角色-权限绑定]:::rbacStyle
    end

    subgraph platformABAC["平台 ABAC 体系"]
        A1[属性定义<br/>tenant, department, env]:::abacStyle
        A2[策略规则]:::abacStyle
        A3[动态鉴权]:::abacStyle
    end

    subgraph studioPerm["Studio 权限适配"]
        S1[功能开关<br/>readonly/edit/admin]:::studioStyle
        S2[数据范围<br/>tenant隔离]:::studioStyle
        S3[操作审计<br/>日志上报]:::studioStyle
    end

    R1 & R2 & R3 -->|权限查询| S1
    A1 & A2 & A3 -->|动态策略| S2
    S1 & S2 -->|操作记录| S3
```

### 7.2 权限粒度设计

| 功能模块 | 权限点 | 说明 |
|----------|--------|------|
| **可视化编排** | `studio:workflow:view` | 查看工作流图 |
| | `studio:workflow:edit` | 编辑工作流节点/连线 |
| | `studio:workflow:deploy` | 部署工作流到运行环境 |
| **调试功能** | `studio:debug:view` | 查看调试会话列表 |
| | `studio:debug:execute` | 启动/停止调试会话 |
| | `studio:debug:trace` | 实时追踪消息流 |
| **配置管理** | `studio:config:view` | 查看 Agent 配置 |
| | `studio:config:edit` | 修改 Agent 配置 |

### 7.3 权限集成代码示例

```typescript
// Studio 组件权限控制
interface StudioPermissions {
  readonly: boolean      // 只读模式
  canEditWorkflow: boolean
  canDeploy: boolean
  canDebug: boolean
  canViewMessageTrace: boolean
}

// 平台向 Studio 注入权限上下文
function StudioContainer() {
  const { user, tenant } = usePlatformContext()
  
  // 查询用户对当前 Agent 的权限
  const permissions = useQuery({
    queryKey: ['studio-permissions', agentId],
    queryFn: () => fetchStudioPermissions(agentId, user.id)
  })
  
  return (
    <StudioWorkflowEditor
      tenantId={tenant.id}
      agentId={agentId}
      permissions={{
        readonly: !permissions.data?.canEdit,
        canEditWorkflow: permissions.data?.canEdit,
        canDeploy: permissions.data?.canDeploy,
        canDebug: permissions.data?.canDebug,
      }}
      // 操作回调由平台拦截进行权限校验
      onDeploy={handleDeploy}
      onSave={handleSave}
    />
  )
}
```

---

## 八、部署与运维方案

### 8.1 部署模式对比

| 模式 | 架构 | 优点 | 缺点 | 推荐场景 |
|------|------|------|------|----------|
| **独立部署** | Studio 单独服务，通过 API 与平台交互 | 解耦彻底、独立扩容、版本独立 | 跨域处理、登录态同步复杂 | Studio 重度使用场景 |
| **内嵌部署** | Studio 作为平台服务模块 | 集成度高、权限统一、用户体验好 | 耦合度高、发布需同步 | 平台深度集成场景 |
| **混合部署** | 前端微前端 + 后端独立服务 | 平衡解耦与体验 | 架构复杂度较高 | **推荐方案** |

### 8.2 推荐部署架构（混合模式）

```mermaid
flowchart TB
    classDef ingressStyle fill:#c6f6d5,stroke:#276749,stroke-width:2px,color:#1c4532
    classDef platformStyle fill:#4299e1,stroke:#2b6cb0,stroke-width:2px,color:#fff
    classDef studioStyle fill:#9f7aea,stroke:#553c9a,stroke-width:2px,color:#fff
    classDef sharedStyle fill:#ed8936,stroke:#c05621,stroke-width:2px,color:#fff

    subgraph ingress["入口层"]
        Nginx[Nginx<br/>路由分发]:::ingressStyle
    end

    subgraph platformFront["平台前端"]
        PF[React App<br/>Vite 构建]:::platformStyle
        MF[Module Federation<br/>运行时加载]:::platformStyle
    end

    subgraph studioFront["Studio 前端"]
        SF[Studio Components<br/>独立构建]:::studioStyle
    end

    subgraph platformBack["平台后端"]
        PB[FastAPI<br/>业务服务]:::platformStyle
    end

    subgraph studioBack["Studio 后端"]
        SB[FastAPI<br/>调试服务]:::studioStyle
    end

    subgraph shared["共享基础设施"]
        Redis[(Redis<br/>会话/缓存)]:::sharedStyle
        PG[(PostgreSQL<br/>数据存储)]:::sharedStyle
        MQ[(RabbitMQ<br/>消息队列)]:::sharedStyle
    end

    Nginx -->|/| PF
    Nginx -->|/studio/*| SB
    Nginx -->|/api/*| PB
    
    PF <-->|动态加载| SF
    PB <-->|数据同步| SB
    
    PB & SB -->|共享| Redis
    PB & SB -->|共享| PG
    PB & SB -->|共享| MQ
```

### 8.3 容器化部署配置

```yaml
# docker-compose.yml 片段
version: '3.8'

services:
  # 平台前端
  platform-web:
    build: ./platform-web
    ports:
      - "3000:80"
    environment:
      - STUDIO_REMOTE_URL=http://studio-web:80/remoteEntry.js

  # Studio 前端（微前端 Remote）
  studio-web:
    build: ./studio-web
    ports:
      - "3001:80"

  # 平台后端
  platform-api:
    build: ./platform-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/platform
      - REDIS_URL=redis://redis:6379
      - STUDIO_API_URL=http://studio-api:8001

  # Studio 后端
  studio-api:
    build: ./studio-api
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/platform
      - REDIS_URL=redis://redis:6379
      - MESSAGE_BUS_URL=amqp://rabbitmq:5672
```

### 8.4 运维监控要点

| 监控项 | 指标 | 告警阈值 |
|--------|------|----------|
| Studio 服务健康 | HTTP 200 比例 | < 99.9% |
| WebSocket 连接数 | 并发连接数 | > 1000 |
| 消息流延迟 | 端到端延迟 P99 | > 500ms |
| 配置同步成功率 | 同步成功比例 | < 99.5% |
| 前端加载性能 | 首屏加载时间 | > 3s |

---

## 九、集成实施路线图

### 9.1 分阶段实施计划

```mermaid
flowchart LR
    classDef p1Style fill:#48bb78,stroke:#276749,stroke-width:2px,color:#fff
    classDef p2Style fill:#4299e1,stroke:#2b6cb0,stroke-width:2px,color:#fff
    classDef p3Style fill:#9f7aea,stroke:#553c9a,stroke-width:2px,color:#fff

    subgraph p1["阶段一（第 1-2 周）：基础集成"]
        P1A[iframe 嵌入模式]:::p1Style
        P1B[基础 API 对接]:::p1Style
        P1C[单租户调试]:::p1Style
    end

    subgraph p2["阶段二（第 3-4 周）：深度集成"]
        P2A[微前端改造]:::p2Style
        P2B[权限体系打通]:::p2Style
        P2C[多租户隔离]:::p2Style
    end

    subgraph p3["阶段三（第 5-6 周）：生产就绪"]
        P3A[性能优化]:::p3Style
        P3B[监控告警]:::p3Style
        P3C[灰度发布]:::p3Style
    end

    p1 --> p2 --> p3
```

### 9.2 各阶段交付物

| 阶段 | 交付物 | 验收标准 |
|------|--------|----------|
| **阶段一** | Studio iframe 嵌入页面 | 可在平台内打开 Studio，进行基础调试 |
| **阶段二** | 微前端集成版本 | 无缝集成体验，权限控制生效 |
| **阶段三** | 生产可用版本 | 性能达标，监控完善，可灰度发布 |

---

## 十、风险与应对

| 风险点 | 影响 | 应对策略 |
|--------|------|----------|
| Studio 版本升级不兼容 | 功能异常 | 定义清晰 API 契约，集成测试覆盖 |
| 消息流数据量大 | 性能下降 | 消息采样、分页加载、WebSocket 压缩 |
| 跨域/登录态问题 | 用户体验差 | 统一 SSO，Token 透传机制 |
| 权限模型差异 | 安全漏洞 | 平台统一鉴权，Studio 只读权限上下文 |
| 微前端加载失败 | 页面白屏 | 降级方案（iframe 兜底）、加载超时处理 |

---

## 十一、附录

### 11.1 相关文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 智能体平台架构设计 | [智能体平台架构设计文档_v0.2.md](./智能体平台架构设计文档_v0.2.md) | 整体架构参考 |
| AgentScope 生态圈 | [agentscope生态圈.md](./agentscope生态圈.md) | Studio 生态定位 |
| LLM Gateway 设计 | [LLM Gateway 模块设计.md](./LLM Gateway 模块设计.md) | API 网关设计参考 |

### 11.2 术语表

| 术语 | 说明 |
|------|------|
| Module Federation | Webpack 微前端方案，支持运行时加载远程模块 |
| Spark Design | AgentScope 官方设计体系 |
| Message Bus | 多智能体消息总线，负责消息路由 |
| HITL | Human-In-The-Loop，人工介入节点 |

---

*本文档为 AgentScope Studio 集成技术详细设计，作为开发实施的依据。*
