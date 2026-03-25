import { useEffect, useRef, useState } from 'react'
import {
  Button, Input, Spin, Tag, Typography, App, Tooltip, Space,
} from 'antd'
import {
  SendOutlined, StopOutlined, ArrowLeftOutlined,
  RobotOutlined, ThunderboltOutlined, ToolOutlined,
} from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { getAgent, type Agent } from '../../api/agents'
import { useAuthStore } from '../../store/auth'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: Array<{ name: string; result: string }>
  streaming?: boolean
}

interface ToolCallRecord {
  name: string
  arguments: Record<string, unknown>
  result: string
}

const TYPE_META: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  chat:  { color: '#4f46e5', label: 'Chat',  icon: <RobotOutlined /> },
  react: { color: '#7c3aed', label: 'ReAct', icon: <ThunderboltOutlined /> },
}

export default function Chat() {
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const token = useAuthStore((s) => s.token)

  const [agent, setAgent] = useState<Agent | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [agentLoading, setAgentLoading] = useState(true)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!agentId) return
    setAgentLoading(true)
    getAgent(agentId)
      .then((res) => setAgent(res.data.data))
      .catch(() => message.error('加载智能体信息失败'))
      .finally(() => setAgentLoading(false))
  }, [agentId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const stopGenerate = () => {
    abortRef.current?.abort()
    setLoading(false)
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      if (last?.streaming) {
        return [...prev.slice(0, -1), { ...last, streaming: false }]
      }
      return prev
    })
  }

  const sendMessage = async () => {
    if (!input.trim() || loading || !agentId) return

    const userContent = input.trim()
    setInput('')

    const newHistory: ChatMessage[] = [...messages, { role: 'user', content: userContent }]
    setMessages(newHistory)
    setLoading(true)

    // 先加一个空的 assistant 占位
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '', streaming: true },
    ])

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const resp = await fetch('/v1/chat/completions', {
        method: 'POST',
        signal: ctrl.signal,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          model: agentId,
          messages: newHistory.map((m) => ({ role: m.role, content: m.content })),
          stream: true,
        }),
      })

      if (!resp.ok) {
        const errText = await resp.text()
        throw new Error(`HTTP ${resp.status}: ${errText}`)
      }

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let accumulated = ''
      let toolCalls: ToolCallRecord[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') break
          try {
            const json = JSON.parse(data)
            const chunk = json.choices?.[0]?.delta?.content
            if (chunk) {
              accumulated += chunk
              setMessages((prev) => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  role: 'assistant',
                  content: accumulated,
                  streaming: true,
                }
                return updated
              })
            }
            // 非流式最终响应的 tool_calls 扩展字段
            if (json.tool_calls?.length) {
              toolCalls = json.tool_calls
            }
          } catch {
            // ignore parse errors
          }
        }
      }

      // 结束：移除 streaming 标记，附上 tool_calls
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: accumulated,
          toolCalls: toolCalls.length > 0 ? toolCalls.map((tc) => ({
            name: tc.name,
            result: tc.result,
          })) : undefined,
          streaming: false,
        }
        return updated
      })
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') return
      console.error(err)
      message.error('发送失败，请检查网络或后端服务')
      // 移除占位消息
      setMessages((prev) => prev.filter((_, i) => i !== prev.length - 1))
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const typeMeta = agent ? (TYPE_META[agent.agent_type] ?? TYPE_META.chat) : TYPE_META.chat

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 64px)',
        background: '#f9fafb',
      }}
    >
      {/* ── 顶部：智能体信息栏 ── */}
      <div
        style={{
          padding: '12px 20px',
          background: '#fff',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <Tooltip title="返回列表">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/agents')}
          />
        </Tooltip>
        <Spin spinning={agentLoading} size="small">
          <Space>
            <div
              style={{
                width: 36, height: 36, borderRadius: 8,
                background: typeMeta.color + '15',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: typeMeta.color, fontSize: 16,
              }}
            >
              {typeMeta.icon}
            </div>
            <div>
              <Typography.Text strong style={{ fontSize: 15 }}>
                {agent?.name ?? '加载中...'}
              </Typography.Text>
              <div>
                <Tag color={typeMeta.color} style={{ fontSize: 11 }}>
                  {typeMeta.label}
                </Tag>
                {agent && (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {(agent.llm_config as { model_name?: string })?.model_name}
                  </Typography.Text>
                )}
              </div>
            </div>
          </Space>
        </Spin>
        <div style={{ marginLeft: 'auto' }}>
          <Button
            size="small"
            type="text"
            danger
            onClick={() => setMessages([])}
          >
            清空对话
          </Button>
        </div>
      </div>

      {/* ── 消息列表区 ── */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: 60, color: '#9ca3af' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>💬</div>
            <Typography.Text type="secondary">
              和 {agent?.name ?? '智能体'} 开始对话吧
            </Typography.Text>
          </div>
        )}
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            {/* 角色标签 */}
            <Typography.Text
              type="secondary"
              style={{ fontSize: 11, marginBottom: 4, paddingLeft: msg.role === 'user' ? 0 : 4 }}
            >
              {msg.role === 'user' ? '你' : agent?.name ?? 'AI'}
            </Typography.Text>

            {/* 气泡 */}
            <div className={`msg-bubble ${msg.role}${msg.streaming ? ' typing-cursor' : ''}`}>
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content || (msg.streaming ? ' ' : '（无内容）')}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>

            {/* 工具调用折叠区 */}
            {msg.toolCalls && msg.toolCalls.length > 0 && (
              <div
                style={{
                  marginTop: 6,
                  maxWidth: '72%',
                  background: '#f3f4f6',
                  border: '1px solid #e5e7eb',
                  borderRadius: 8,
                  padding: '8px 12px',
                  fontSize: 12,
                  color: '#6b7280',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 4, color: '#4f46e5' }}>
                  <ToolOutlined /> 工具调用 ({msg.toolCalls.length})
                </div>
                {msg.toolCalls.map((tc, i) => (
                  <div key={i} style={{ marginBottom: 4 }}>
                    <Tag color="purple" style={{ fontSize: 11 }}>{tc.name}</Tag>
                    <span style={{ color: '#9ca3af' }}>{tc.result.slice(0, 120)}{tc.result.length > 120 ? '…' : ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* ── 输入区 ── */}
      <div
        style={{
          padding: '12px 16px',
          background: '#fff',
          borderTop: '1px solid #e5e7eb',
          display: 'flex',
          gap: 8,
          alignItems: 'flex-end',
        }}
      >
        <Input.TextArea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息... （Enter 发送，Shift+Enter 换行）"
          autoSize={{ minRows: 1, maxRows: 6 }}
          disabled={loading}
          style={{ flex: 1, resize: 'none', borderRadius: 8 }}
        />
        {loading ? (
          <Tooltip title="停止生成">
            <Button
              danger
              icon={<StopOutlined />}
              onClick={stopGenerate}
              style={{ height: 36 }}
            />
          </Tooltip>
        ) : (
          <Tooltip title="发送 (Enter)">
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={sendMessage}
              disabled={!input.trim()}
              style={{ height: 36 }}
            />
          </Tooltip>
        )}
      </div>
    </div>
  )
}
