/**
 * 凭据保险箱：浏览器 localStorage。
 *
 * 两种模式：
 * - 明文模式（默认）：plaintext data 直接存
 * - 加密模式（M3）：用主密码 PBKDF2+AES-GCM 加密后存；运行时需先解锁
 *
 * 切换：在 VaultDialog 里勾选「启用加密」 → 设主密码 → 之后存的都是密文。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { encryptPayload, decryptPayload, isEncryptedPayload } from '../utils/crypto'

const KEY = 'app-for-oneself-creds'
const MAX_RECENT = 10

function readRaw() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}')
  } catch {
    return {}
  }
}

function writeRaw(obj) {
  localStorage.setItem(KEY, JSON.stringify(obj))
}

export const useVaultStore = defineStore('vault', () => {
  const raw = ref(readRaw())                // localStorage 实际内容（可能是密文）
  const data = ref({})                       // 解密后的明文（仅在运行时存在）
  const password = ref('')                   // 解锁后保留在内存，便于后续写入时重新加密
  const locked = ref(false)                  // 是否处于"已加密但未解锁"状态

  // 初始化：若 raw 是密文，则 locked=true 等用户解锁；否则直接作为明文用
  if (isEncryptedPayload(raw.value)) {
    locked.value = true
  } else {
    data.value = { ...raw.value }
  }

  const isEncrypted = computed(() => isEncryptedPayload(raw.value))
  const githubToken = computed(() => data.value.github_token || '')
  const aiProvider = computed(() => data.value.ai_provider || 'deepseek')
  const aiKey = computed(() => data.value.ai_key || '')
  const aiModel = computed(() => data.value.ai_model || '')
  const repo = computed(() => data.value.repo || '')
  const recentRepos = computed(() => data.value.recent_repos || [])
  const configured = computed(
    () => !locked.value && Boolean(data.value.github_token && data.value.ai_key)
  )

  async function persist() {
    if (password.value) {
      // 加密模式
      const payload = await encryptPayload(JSON.stringify(data.value), password.value)
      raw.value = payload
      writeRaw(payload)
    } else {
      // 明文模式
      raw.value = { ...data.value }
      writeRaw(raw.value)
    }
  }

  async function update(patch) {
    if (locked.value) throw new Error('vault is locked')
    data.value = { ...data.value, ...patch }
    await persist()
  }

  async function switchRepo(newRepo) {
    if (!newRepo || locked.value) return
    const recent = (data.value.recent_repos || []).filter((r) => r !== newRepo)
    recent.unshift(newRepo)
    data.value = {
      ...data.value,
      repo: newRepo,
      recent_repos: recent.slice(0, MAX_RECENT),
    }
    await persist()
  }

  async function removeRecent(target) {
    if (locked.value) return
    data.value = {
      ...data.value,
      recent_repos: (data.value.recent_repos || []).filter((r) => r !== target),
    }
    await persist()
  }

  async function clear() {
    raw.value = {}
    data.value = {}
    password.value = ''
    locked.value = false
    localStorage.removeItem(KEY)
  }

  // ============== 加密/解锁 ==============

  /** 解锁已加密 vault。成功后 data 可用。 */
  async function unlock(pwd) {
    if (!locked.value) return
    const plaintextStr = await decryptPayload(raw.value, pwd)
    data.value = JSON.parse(plaintextStr)
    password.value = pwd
    locked.value = false
  }

  /** 启用加密：从明文转密文。 */
  async function enableEncryption(pwd) {
    if (locked.value) throw new Error('请先解锁')
    if (!pwd || pwd.length < 6) throw new Error('密码至少 6 位')
    password.value = pwd
    await persist()
  }

  /** 关闭加密：从密文转明文。 */
  async function disableEncryption() {
    if (locked.value) throw new Error('请先解锁')
    password.value = ''
    await persist()
  }

  /** 改密码：要求当前密码已在内存中（已解锁状态）。 */
  async function changePassword(newPwd) {
    if (locked.value) throw new Error('请先解锁')
    if (!newPwd || newPwd.length < 6) throw new Error('新密码至少 6 位')
    password.value = newPwd
    await persist()
  }

  function authHeaders() {
    if (locked.value) return {}
    const h = {}
    if (data.value.github_token) h['X-GitHub-Token'] = data.value.github_token
    if (data.value.ai_provider) h['X-AI-Provider'] = data.value.ai_provider
    if (data.value.ai_key) h['X-AI-Key'] = data.value.ai_key
    if (data.value.ai_model) h['X-AI-Model'] = data.value.ai_model
    if (data.value.repo) h['X-Repo'] = data.value.repo
    return h
  }

  return {
    data, raw, locked, isEncrypted,
    githubToken, aiProvider, aiKey, aiModel, repo, recentRepos, configured,
    update, switchRepo, removeRecent, clear, authHeaders,
    unlock, enableEncryption, disableEncryption, changePassword,
  }
})
