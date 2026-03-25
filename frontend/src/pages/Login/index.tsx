import { useState } from 'react'
import { Card, Form, Input, Button, Typography, Tabs, App, Divider } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined, TeamOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { login, register, getMe } from '../../api/auth'
import { useAuthStore } from '../../store/auth'

export default function Login() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [loginForm] = Form.useForm()
  const [regForm] = Form.useForm()

  const handleLogin = async (values: { email: string; password: string }) => {
    setLoading(true)
    try {
      const res = await login(values)
      const { access_token } = res.data.data
      const meRes = await getMe(access_token)
      setAuth(access_token, meRes.data.data)
      message.success('登录成功')
      navigate('/agents')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? '登录失败，请检查邮箱和密码')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (values: {
    email: string
    password: string
    display_name: string
    tenant_name: string
  }) => {
    setLoading(true)
    try {
      await register(values)
      message.success('注册成功，请登录')
      setTab('login')
      loginForm.setFieldValue('email', values.email)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg ?? '注册失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%)',
      }}
    >
      <Card
        style={{ width: 420, boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}
        styles={{ body: { padding: '32px 36px' } }}
      >
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🤖</div>
          <Typography.Title level={3} style={{ margin: 0, color: '#1e1b4b' }}>
            AgentBase Platform
          </Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            智能体平台 MVP
          </Typography.Text>
        </div>

        <Tabs
          activeKey={tab}
          onChange={(k) => setTab(k as 'login' | 'register')}
          centered
          items={[
            { key: 'login', label: '登录' },
            { key: 'register', label: '注册' },
          ]}
          style={{ marginBottom: 4 }}
        />

        {tab === 'login' && (
          <Form form={loginForm} onFinish={handleLogin} size="large" layout="vertical">
            <Form.Item
              name="email"
              rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}
            >
              <Input prefix={<MailOutlined />} placeholder="邮箱" />
            </Form.Item>
            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password prefix={<LockOutlined />} placeholder="密码" />
            </Form.Item>
            <Form.Item style={{ marginBottom: 0 }}>
              <Button type="primary" htmlType="submit" block loading={loading}>
                登录
              </Button>
            </Form.Item>
          </Form>
        )}

        {tab === 'register' && (
          <Form form={regForm} onFinish={handleRegister} size="large" layout="vertical">
            <Form.Item
              name="email"
              rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}
            >
              <Input prefix={<MailOutlined />} placeholder="邮箱" />
            </Form.Item>
            <Form.Item
              name="password"
              rules={[{ required: true, min: 6, message: '密码至少 6 位' }]}
            >
              <Input.Password prefix={<LockOutlined />} placeholder="密码（至少 6 位）" />
            </Form.Item>
            <Form.Item name="display_name" rules={[{ required: true, message: '请输入昵称' }]}>
              <Input prefix={<UserOutlined />} placeholder="昵称" />
            </Form.Item>
            <Form.Item name="tenant_name" rules={[{ required: true, message: '请输入团队名称' }]}>
              <Input prefix={<TeamOutlined />} placeholder="团队名称" />
            </Form.Item>
            <Form.Item style={{ marginBottom: 0 }}>
              <Button type="primary" htmlType="submit" block loading={loading}>
                注册
              </Button>
            </Form.Item>
          </Form>
        )}

        <Divider style={{ margin: '20px 0 12px' }} />
        <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', textAlign: 'center' }}>
          powered by AgentScope + FastAPI
        </Typography.Text>
      </Card>
    </div>
  )
}
