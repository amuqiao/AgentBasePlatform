import { useEffect, useState } from 'react'
import {
  Card, Row, Col, Typography, Tag, Button, Space, Empty,
  Spin, Badge, Tooltip, App,
} from 'antd'
import {
  RobotOutlined, MessageOutlined, ThunderboltOutlined,
  PlusOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { listAgents, type Agent } from '../../api/agents'

const TYPE_META: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  chat:  { color: '#4f46e5', label: 'Chat',   icon: <MessageOutlined /> },
  react: { color: '#7c3aed', label: 'ReAct',  icon: <ThunderboltOutlined /> },
  task:  { color: '#059669', label: 'Task',   icon: <RobotOutlined /> },
}

const STATUS_MAP: Record<string, { status: 'success' | 'default'; text: string }> = {
  published: { status: 'success', text: '已发布' },
  draft:     { status: 'default', text: '草稿' },
}

export default function Agents() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)

  const fetchAgents = async () => {
    setLoading(true)
    try {
      const res = await listAgents(1, 50)
      setAgents(res.data.data.items)
    } catch {
      message.error('获取智能体列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAgents() }, [])

  const typeMeta = (type: string) => TYPE_META[type] ?? { color: '#6b7280', label: type, icon: <RobotOutlined /> }

  return (
    <div style={{ padding: 24 }}>
      {/* 页头 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>智能体管理</Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            共 {agents.length} 个智能体
          </Typography.Text>
        </div>
        <Space>
          <Tooltip title="刷新">
            <Button icon={<ReloadOutlined />} onClick={fetchAgents} loading={loading} />
          </Tooltip>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => message.info('创建功能即将上线')}
          >
            新建智能体
          </Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        {agents.length === 0 && !loading ? (
          <Empty description="暂无智能体，点击「新建智能体」开始" style={{ marginTop: 80 }} />
        ) : (
          <Row gutter={[16, 16]}>
            {agents.map((agent) => {
              const meta = typeMeta(agent.agent_type)
              const statusInfo = STATUS_MAP[agent.status] ?? { status: 'default' as const, text: agent.status }
              const modelName = (agent.llm_config as { model_name?: string })?.model_name ?? '—'

              return (
                <Col key={agent.id} xs={24} sm={12} lg={8} xl={6}>
                  <Card
                    hoverable
                    style={{ height: '100%', borderRadius: 12 }}
                    styles={{ body: { padding: 20 } }}
                    actions={[
                      <Button
                        key="chat"
                        type="link"
                        icon={<MessageOutlined />}
                        onClick={() => navigate(`/chat/${agent.id}`)}
                      >
                        开始对话
                      </Button>,
                    ]}
                  >
                    {/* 顶部：图标 + 类型 + 状态 */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                      <div
                        style={{
                          width: 40, height: 40, borderRadius: 10,
                          background: meta.color + '15',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: meta.color, fontSize: 18,
                        }}
                      >
                        {meta.icon}
                      </div>
                      <Space size={4}>
                        <Tag color={meta.color} style={{ margin: 0 }}>{meta.label}</Tag>
                        <Badge status={statusInfo.status} text={statusInfo.text} />
                      </Space>
                    </div>

                    {/* 名称 + 描述 */}
                    <Typography.Text strong style={{ display: 'block', fontSize: 15, marginBottom: 4 }}>
                      {agent.name}
                    </Typography.Text>
                    <Typography.Text
                      type="secondary"
                      style={{ fontSize: 12, display: 'block', marginBottom: 12 }}
                      ellipsis={{ tooltip: agent.description }}
                    >
                      {agent.description || '暂无描述'}
                    </Typography.Text>

                    {/* 元信息 */}
                    <div style={{ display: 'flex', gap: 12, fontSize: 12, color: '#9ca3af' }}>
                      <span>v{agent.current_version}</span>
                      <span title="模型">🧠 {modelName}</span>
                    </div>
                  </Card>
                </Col>
              )
            })}
          </Row>
        )}
      </Spin>
    </div>
  )
}
