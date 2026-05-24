/**
 * 凭据保险箱：浏览器 localStorage 存 token / API key / repo。
 *
 * 这是 M1 最简实现：明文存。M2 加 WebCrypto + 口令加密。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const KEY = 'app-for-oneself-creds'

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}')
  } catch {
    return {}
  }
}

function save(obj) {
  localStorage.setItem(KEY, JSON.stringify(obj))
}

export const useVaultStore = defineStore('vault', () => {
  const data = ref(load())

  const githubToken = computed(() => data.value.github_token || '')
  const aiProvider = computed(() => data.value.ai_provider || 'deepseek')
  const aiKey = computed(() => data.value.ai_key || '')
  const aiModel = computed(() => data.value.ai_model || '')
  const repo = computed(() => data.value.repo || '')
  const configured = computed(() => Boolean(data.value.github_token && data.value.ai_key))

  function update(patch) {
    data.value = { ...data.value, ...patch }
    save(data.value)
  }

  function clear() {
    data.value = {}
    localStorage.removeItem(KEY)
  }

  function authHeaders() {
    const h = {}
    if (data.value.github_token) h['X-GitHub-Token'] = data.value.github_token
    if (data.value.ai_provider) h['X-AI-Provider'] = data.value.ai_provider
    if (data.value.ai_key) h['X-AI-Key'] = data.value.ai_key
    if (data.value.ai_model) h['X-AI-Model'] = data.value.ai_model
    if (data.value.repo) h['X-Repo'] = data.value.repo
    return h
  }

  return { data, githubToken, aiProvider, aiKey, aiModel, repo, configured, update, clear, authHeaders }
})
