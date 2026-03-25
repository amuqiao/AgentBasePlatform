import client from './client'

export interface Agent {
  id: string
  name: string
  description: string
  agent_type: 'chat' | 'react' | 'task'
  status: string
  current_version: number
  llm_config: Record<string, unknown>
  tool_config: Record<string, unknown>
  created_at: string
}

export interface OpenAIModel {
  id: string
  object: 'model'
  name: string
  agent_type: string
  owned_by: string
}

export const listAgents = (page = 1, pageSize = 20) =>
  client.get<{
    code: number
    data: { items: Agent[]; total: number; page: number; page_size: number }
  }>('/api/v1/agents', { params: { page, page_size: pageSize } })

export const getAgent = (id: string) =>
  client.get<{ code: number; data: Agent }>(`/api/v1/agents/${id}`)

export const listModels = () =>
  client.get<{ object: 'list'; data: OpenAIModel[] }>('/v1/models')

export const createAgent = (payload: {
  name: string
  description?: string
  agent_type?: string
  system_prompt?: string
  llm_config?: Record<string, unknown>
}) => client.post<{ code: number; data: Agent }>('/api/v1/agents', payload)

export const publishAgent = (id: string, note = '') =>
  client.post(`/api/v1/agents/${id}/publish`, { publish_note: note })
