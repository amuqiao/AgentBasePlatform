import client from './client'

export interface LoginPayload {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export const login = (payload: LoginPayload) =>
  client.post<{ code: number; data: TokenResponse }>('/api/v1/auth/login', payload)

export const register = (payload: {
  email: string
  password: string
  display_name: string
  tenant_name: string
}) => client.post('/api/v1/auth/register', payload)

export const getMe = (token?: string) =>
  client.get<{ code: number; data: { id: string; email: string; display_name: string; tenant_id: string; role: string } }>(
    '/api/v1/auth/me',
    token ? { headers: { Authorization: `Bearer ${token}` } } : undefined,
  )
