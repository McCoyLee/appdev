import axios from 'axios'
import { useVaultStore } from '../stores/vault'

export const http = axios.create({
  baseURL: '',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  try {
    const vault = useVaultStore()
    Object.assign(config.headers, vault.authHeaders())
  } catch {
    // Pinia 还没初始化（极端早期调用），忽略
  }
  return config
})

export const repoApi = {
  info: (repo) => http.get('/api/repo/info', { params: { repo } }),
  tree: (path = '', ref, repo) => http.get('/api/repo/tree', { params: { path, ref, repo } }),
  file: (path, ref, repo) => http.get('/api/repo/file', { params: { path, ref, repo } }),
}

export const secretsApi = {
  list: (repo) => http.get('/api/secrets', { params: { repo } }),
  set: (name, value, repo) => http.post('/api/secrets', { name, value }, { params: { repo } }),
  remove: (name, repo) => http.delete(`/api/secrets/${name}`, { params: { repo } }),
}

export const actionsApi = {
  workflows: (repo) => http.get('/api/workflows', { params: { repo } }),
  runs: (workflow, per_page = 10, repo) =>
    http.get('/api/runs', { params: { workflow, per_page, repo } }),
  dispatch: (workflow, ref = 'main', inputs = {}, repo) =>
    http.post('/api/runs/dispatch', { workflow, ref, inputs }, { params: { repo } }),
}

export const previewApi = {
  status: (branch, repo) => http.get('/api/preview', { params: { branch, repo } }),
  trigger: (branch, repo) => http.post('/api/preview/trigger', null, { params: { branch, repo } }),
  setupEnvironment: (repo) => http.post('/api/preview/setup-environment', null, { params: { repo } }),
}

export const branchesApi = {
  list: (repo) => http.get('/api/branches', { params: { repo } }),
  adopt: (branch, target = 'main', repo) =>
    http.post(`/api/branches/${encodeURIComponent(branch)}/adopt`, { target, dispatch_pages: true }, { params: { repo } }),
  discard: (branch, repo) => http.post('/api/branches/discard', { branch }, { params: { repo } }),
}

export const prsApi = {
  list: (state = 'open', repo) => http.get('/api/prs', { params: { state, repo } }),
  get: (number, repo) => http.get(`/api/prs/${number}`, { params: { repo } }),
  create: (body, repo) => http.post('/api/prs', body, { params: { repo } }),
  comment: (number, text, repo) =>
    http.post(`/api/prs/${number}/comment`, { body: text }, { params: { repo } }),
  reviewComment: (number, { path, line, body, side = 'RIGHT' }, repo) =>
    http.post(`/api/prs/${number}/review-comment`, { path, line, body, side }, { params: { repo } }),
  merge: (number, method = 'squash', repo) =>
    http.post(`/api/prs/${number}/merge`, { method, delete_branch: true, dispatch_pages: true }, { params: { repo } }),
  close: (number, repo) => http.post(`/api/prs/${number}/close`, null, { params: { repo } }),
}

export const templatesApi = {
  list: () => http.get('/api/templates'),
  get: (id) => http.get(`/api/templates/${id}`),
}

export const projectsApi = {
  create: (body) => http.post('/api/projects/create', body, { timeout: 60000 }),
  init: (body) => http.post('/api/projects/init', body, { timeout: 60000 }),
}

export const probeApi = {
  github: () => http.get('/api/probe/github', { timeout: 10000 }),
  myRepos: () => http.get('/api/probe/github/repos', { timeout: 10000 }),
  ai: () => http.post('/api/probe/ai', null, { timeout: 30000 }),
}

export const health = () => http.get('/healthz')
