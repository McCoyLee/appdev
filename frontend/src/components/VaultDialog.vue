<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { useVaultStore } from '../stores/vault'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'saved'])

const vault = useVaultStore()
const form = ref({
  github_token: '',
  ai_provider: 'deepseek',
  ai_key: '',
  ai_model: '',
  repo: '',
})

const githubProbe = ref({ status: 'idle', user: null, error: '' })
const aiProbe = ref({ status: 'idle', sample: '', error: '' })
const repos = ref([])
const loadingRepos = ref(false)

// 加密相关
const enableCrypto = ref(false)
const newPassword = ref('')
const confirmPassword = ref('')

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.value = { ...form.value, ...vault.data }
      enableCrypto.value = vault.isEncrypted
      newPassword.value = ''
      confirmPassword.value = ''
      githubProbe.value = { status: 'idle', user: null, error: '' }
      aiProbe.value = { status: 'idle', sample: '', error: '' }
    }
  }
)

function formHeaders() {
  const h = {}
  if (form.value.github_token) h['X-GitHub-Token'] = form.value.github_token
  if (form.value.ai_provider) h['X-AI-Provider'] = form.value.ai_provider
  if (form.value.ai_key) h['X-AI-Key'] = form.value.ai_key
  if (form.value.ai_model) h['X-AI-Model'] = form.value.ai_model
  return h
}

async function probeGithub() {
  if (!form.value.github_token.trim()) {
    githubProbe.value = { status: 'fail', user: null, error: '先填 token' }
    return
  }
  githubProbe.value = { status: 'running', user: null, error: '' }
  try {
    const { data } = await axios.get('/api/probe/github', { headers: formHeaders(), timeout: 10000 })
    githubProbe.value = { status: 'ok', user: data, error: '' }
    await loadRepos()
  } catch (e) {
    githubProbe.value = { status: 'fail', user: null, error: e.response?.data?.detail || e.message }
  }
}

async function loadRepos() {
  loadingRepos.value = true
  try {
    const { data } = await axios.get('/api/probe/github/repos', { headers: formHeaders(), timeout: 10000 })
    repos.value = data.repos || []
  } catch (e) { /* ignore */ }
  finally { loadingRepos.value = false }
}

async function probeAi() {
  if (!form.value.ai_key.trim()) {
    aiProbe.value = { status: 'fail', sample: '', error: '先填 AI key' }
    return
  }
  aiProbe.value = { status: 'running', sample: '', error: '' }
  try {
    const { data } = await axios.post('/api/probe/ai', null, { headers: formHeaders(), timeout: 30000 })
    aiProbe.value = { status: 'ok', sample: data.sample_reply, error: '' }
  } catch (e) {
    aiProbe.value = { status: 'fail', sample: '', error: e.response?.data?.detail || e.message }
  }
}

const canSave = computed(() => {
  if (enableCrypto.value && !vault.isEncrypted) {
    // 启用加密时必须设密码
    if (!newPassword.value || newPassword.value.length < 6) return false
    if (newPassword.value !== confirmPassword.value) return false
  }
  return (
    form.value.github_token.trim() &&
    form.value.ai_key.trim() &&
    /^[^/]+\/[^/]+$/.test(form.value.repo || '')
  )
})

async function save() {
  if (!form.value.github_token.trim()) return ElMessage.warning('请填 GitHub token')
  if (!form.value.ai_key.trim()) return ElMessage.warning('请填 AI key')
  if (!/^[^/]+\/[^/]+$/.test(form.value.repo || '')) return ElMessage.warning('repo 格式应为 owner/name')

  try {
    // 1. 写明文 data
    await vault.update({ ...form.value })
    await vault.switchRepo(form.value.repo)

    // 2. 处理加密状态切换
    if (enableCrypto.value && !vault.isEncrypted) {
      if (newPassword.value.length < 6) {
        return ElMessage.warning('密码至少 6 位')
      }
      if (newPassword.value !== confirmPassword.value) {
        return ElMessage.warning('两次密码不一致')
      }
      await vault.enableEncryption(newPassword.value)
      ElMessage.success('已加密保存')
    } else if (!enableCrypto.value && vault.isEncrypted) {
      await ElMessageBox.confirm('确定关闭加密？凭据将明文存在浏览器。', '警告', { type: 'warning' })
      await vault.disableEncryption()
      ElMessage.success('已切回明文存储')
    } else if (enableCrypto.value && vault.isEncrypted && newPassword.value) {
      // 已加密状态下改密码
      if (newPassword.value.length < 6) return ElMessage.warning('新密码至少 6 位')
      if (newPassword.value !== confirmPassword.value) return ElMessage.warning('两次密码不一致')
      await vault.changePassword(newPassword.value)
      ElMessage.success('密码已更新')
    } else {
      ElMessage.success('已保存')
    }

    emit('update:modelValue', false)
    emit('saved')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

async function clear() {
  try {
    await ElMessageBox.confirm('清空所有本地凭据？', '警告', { type: 'warning' })
    await vault.clear()
    ElMessage.success('已清空')
    emit('update:modelValue', false)
    location.reload()
  } catch {}
}

function probeIconType(status) {
  if (status === 'ok') return 'success'
  if (status === 'fail') return 'danger'
  if (status === 'running') return 'warning'
  return 'info'
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="(v) => emit('update:modelValue', v)"
    title="凭据配置"
    width="640px"
  >
    <el-alert
      :type="vault.isEncrypted ? 'success' : 'info'"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
    >
      {{ vault.isEncrypted
        ? '当前已加密存储。每次启动需输入主密码解锁。'
        : '凭据保存在浏览器 localStorage（明文）。可在下方启用加密提高安全性。'
      }}
    </el-alert>

    <el-form label-width="120px" label-position="top">
      <!-- GitHub Token -->
      <el-form-item label="GitHub Token">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-input v-model="form.github_token" type="password" show-password placeholder="fine-grained PAT" style="flex: 1" />
          <el-button :loading="githubProbe.status === 'running'" @click="probeGithub">测试</el-button>
        </div>
        <div v-if="githubProbe.status !== 'idle'" class="probe-result">
          <el-tag :type="probeIconType(githubProbe.status)" size="small">
            {{ githubProbe.status === 'ok' ? `✓ ${githubProbe.user.login}` : (githubProbe.status === 'running' ? '验证中...' : '✗ 失败') }}
          </el-tag>
          <span v-if="githubProbe.error" class="err">{{ githubProbe.error }}</span>
        </div>
        <div class="hint">
          需要 Contents / Pull requests / Actions / Workflows / Secrets R/W 权限。
          <el-link href="https://github.com/settings/personal-access-tokens/new" target="_blank" type="primary">
            创建 ↗
          </el-link>
        </div>
      </el-form-item>

      <!-- AI -->
      <el-form-item label="AI Provider">
        <el-radio-group v-model="form.ai_provider">
          <el-radio value="deepseek">DeepSeek（推荐）</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="AI Key">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-input v-model="form.ai_key" type="password" show-password placeholder="sk-..." style="flex: 1" />
          <el-button :loading="aiProbe.status === 'running'" @click="probeAi">测试</el-button>
        </div>
        <div v-if="aiProbe.status !== 'idle'" class="probe-result">
          <el-tag :type="probeIconType(aiProbe.status)" size="small">
            {{ aiProbe.status === 'ok' ? `✓ ${aiProbe.sample}` : (aiProbe.status === 'running' ? '验证中...' : '✗ 失败') }}
          </el-tag>
          <span v-if="aiProbe.error" class="err">{{ aiProbe.error }}</span>
        </div>
        <div class="hint">
          <el-link href="https://platform.deepseek.com/api_keys" target="_blank" type="primary">创建 Key ↗</el-link>
          （约 ¥10 玩一个月）
        </div>
      </el-form-item>

      <el-form-item label="AI 模型（可选）">
        <el-input v-model="form.ai_model" placeholder="deepseek-chat" />
      </el-form-item>

      <!-- Repo -->
      <el-form-item label="当前仓库">
        <el-select v-model="form.repo" filterable allow-create default-first-option placeholder="选一个或手动输入" style="width: 100%">
          <el-option v-for="r in repos" :key="r.full_name" :label="r.full_name + (r.private ? ' 🔒' : '')" :value="r.full_name">
            <span>{{ r.full_name }}</span>
            <el-tag v-if="r.private" size="small" type="info" style="margin-left: 8px">私有</el-tag>
          </el-option>
        </el-select>
        <div class="hint">测试 GitHub 后会自动列出可访问仓库</div>
      </el-form-item>

      <!-- 加密设置 -->
      <el-divider>安全</el-divider>

      <el-form-item>
        <el-checkbox v-model="enableCrypto">启用主密码加密存储</el-checkbox>
        <div class="hint">加密后每次启动需输密码解锁；忘了密码无法恢复（只能清空重填）</div>
      </el-form-item>

      <template v-if="enableCrypto">
        <el-form-item :label="vault.isEncrypted ? '新主密码（留空 = 不改）' : '设置主密码（至少 6 位）'">
          <el-input v-model="newPassword" type="password" show-password />
        </el-form-item>
        <el-form-item v-if="newPassword" label="再输一次">
          <el-input v-model="confirmPassword" type="password" show-password />
        </el-form-item>
      </template>
    </el-form>

    <template #footer>
      <el-button @click="clear" type="danger" plain>清空凭据</el-button>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :disabled="!canSave" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.probe-result { margin-top: 6px; display: flex; align-items: center; gap: 8px; }
.err { color: #ef4444; font-size: 12px; }
.hint { color: #6b7280; font-size: 12px; margin-top: 4px; }
</style>
