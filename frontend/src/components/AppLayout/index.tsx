import { Layout, Menu, Avatar, Dropdown, Typography, Space } from 'antd'
import {
  RobotOutlined,
  MessageOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'

const { Header, Sider, Content } = Layout

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, clearAuth } = useAuthStore()

  const selectedKey = location.pathname.startsWith('/chat') ? 'chat' : 'agents'

  const menuItems = [
    {
      key: 'agents',
      icon: <RobotOutlined />,
      label: '智能体管理',
      onClick: () => navigate('/agents'),
    },
    {
      key: 'chat',
      icon: <MessageOutlined />,
      label: '对话广场',
      onClick: () => navigate('/agents'),
    },
  ]

  const userMenu = {
    items: [
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        onClick: () => {
          clearAuth()
          navigate('/login')
        },
      },
    ],
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={220}
        style={{
          background: '#1e1b4b',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
      >
        {/* Logo */}
        <div
          style={{
            padding: '20px 24px',
            color: '#fff',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          <Typography.Text strong style={{ color: '#fff', fontSize: 16 }}>
            🤖 AgentBase
          </Typography.Text>
          <Typography.Text
            style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, display: 'block', marginTop: 2 }}
          >
            MVP Platform
          </Typography.Text>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          style={{
            background: 'transparent',
            border: 'none',
            marginTop: 8,
          }}
          theme="dark"
        />
      </Sider>

      <Layout style={{ marginLeft: 220 }}>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            borderBottom: '1px solid #f0f0f0',
            position: 'sticky',
            top: 0,
            zIndex: 99,
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          }}
        >
          <Dropdown menu={userMenu} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <Avatar icon={<UserOutlined />} style={{ background: '#4f46e5' }} />
              <Typography.Text>{user?.display_name ?? user?.email}</Typography.Text>
            </Space>
          </Dropdown>
        </Header>

        <Content style={{ background: '#f5f5f5', minHeight: 'calc(100vh - 64px)' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
