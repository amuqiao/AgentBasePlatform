import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import AppLayout from '../components/AppLayout'
import Login from '../pages/Login'
import Agents from '../pages/Agents'
import Chat from '../pages/Chat'

function RequireAuth() {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <Outlet />
}

const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/', element: <Navigate to="/agents" replace /> },
          { path: '/agents', element: <Agents /> },
          { path: '/chat/:agentId', element: <Chat /> },
        ],
      },
    ],
  },
])

export default router
