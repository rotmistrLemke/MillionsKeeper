import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT if stored
client.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('mk_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Redirect to login on 401
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      sessionStorage.removeItem('mk_token')
      window.dispatchEvent(new CustomEvent('mk:logout'))
    }
    return Promise.reject(err)
  }
)

export default client
