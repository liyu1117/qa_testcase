import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message
    console.error('API Error:', msg)
    return Promise.reject(error)
  },
)

export function uploadGenerationResult(jobId: number, format: 'md' | 'xmind') {
  return api.post(`/generation/jobs/${jobId}/upload`, null, {
    params: { format },
  })
}

export function downloadGenerationResult(jobId: number, format: 'md' | 'xmind') {
  return `${api.defaults.baseURL}/generation/jobs/${jobId}/download?format=${format}`
}

export default api
