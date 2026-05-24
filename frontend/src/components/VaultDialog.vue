<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
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

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.value = { ...form.value, ...vault.data }
      githubProbe.value = { status: 'idle', user: null, error: '' }
      aiProbe.value = { status: 'idle', sample: '', error: '' }
    }
  }
)

// 用当前 form 里的值发请求（不依赖已保存的 vault state）
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
    const { data } = await axios.get('/api/probe/github', {
      headers: formHeaders(),
      timeout: 10000,
    })
    githubProbe.value = { status: 'ok', user: data, error: '' }
    // 顺便拉仓库列表
    await loadRepos()
  } catch (e) {
    githubProbe.value = {
      status: 'fail',
      user: null,
      error: e.response?.data?.detail || e.message,
    }
  }
}

async function loadRepos() {
  loadingRepos.value = true
  try {
    const { data } = await axios.get('/api/probe/github/repos', {
      headers: formHeaders(),
      timeout: 10000,
    })
    repos.value = data.repos || []
  } catch (e) {
    // 静默
  } finally {
    loadingRepos.value = false
  }
}

async function probeAi() {
  if (!form.value.ai_key.trim()) {
    aiProbe.value = { status: 'fail', sample: '', error: '先填 AI key' }
    return
  }
  aiProbe.value = { status: 'running', sample: '', error: '' }
  try {
    const { data } = await axios.post('/api/probe/ai', null, {
      headers: formHeaders(),
      timeout: 30000,
    })
    aiProbe.value = { status: 'ok', sample: data.sample_reply, error: '' }
  } catch (e) {
    aiProbe.value = {
      status: 'fail',
      sample: '',
      error: e.response?.data?.detail || e.message,
    }
  }
}

const canSave = computed(() => {
  return (
    form.value.github_token.trim() &&
    form.value.ai_key.trim() &&
    /^[^/]+\/[^/]+$/.test(form.value.repo || '')
  )
})

function save() {
  if (!form.value.github_token.trim()) return ElMessage.warning('请填 GitHub token')
  if (!form.value.ai_key.trim()) return ElMessage.warning('请填 AI key')
  if (!/^[^/]+\/[^/]+$/.test(form.value.repo || '')) {
    return ElMessage.warning('repo 格式应为 owner/name')
  }
  vault.update({ ...form.value })
  vault.switchRepo(form.value.repo)
  ElMessage.success('已保存（浏览器本地）')
  emit('update:modelValue', false)
  emit('saved')
}

function clear() {
  vault.clear()
  ElMessage.success('已清空，刷新页面')
  emit('update:modelValue', false)
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
    width="600px"
  >
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
      凭据保存在浏览器 localStorage（明文）。后端不持久化。每个字段右侧的【测试】按钮可立即验证。
    </el-alert>

    <el-form label-width="120px" label-position="top">
      <!-- GitHub Token -->
      <el-form-item label="GitHub Token">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-input
            v-model="form.github_token"
            type="password"
            show-password
            placeholder="fine-grained PAT，去 github.com/settings/personal-access-tokens 创建"
            style="flex: 1"
          />
          <el-button :loading="githubProbe.status === 'running'" @click="probeGithub">
            测试
          </el-button>
        </div>
        <div v-if="githubProbe.status !== 'idle'" class="probe-result">
          <el-tag :type="probeIconType(githubProbe.status)" size="small">
            {{ githubProbe.status === 'ok' ? `✓ ${githubProbe.user.login}` : (githubProbe.status === 'running' ? '验证中...' : '✗ 失败') }}
          </el-tag>
          <span v-if="githubProbe.error" class="err">{{ githubProbe.error }}</span>
        </div>
        <div class="hint">
          需要权限：Contents / Pull requests / Actions / Workflows / Secrets R/W。
          <el-link href="https://github.com/settings/personal-access-tokens/new" target="_blank" type="primary">
            创建 PAT ↗
          </el-link>
        </div>
      </el-form-item>

      <!-- AI Key -->
      <el-form-item label="AI Provider">
        <el-radio-group v-model="form.ai_provider">
          <el-radio value="deepseek">DeepSeek（推荐）</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="AI Key">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-input
            v-model="form.ai_key"
            type="password"
            show-password
            placeholder="sk-... 开头"
            style="flex: 1"
          />
          <el-button :loading="aiProbe.status === 'running'" @click="probeAi">
            测试
          </el-button>
        </div>
        <div v-if="aiProbe.status !== 'idle'" class="probe-result">
          <el-tag :type="probeIconType(aiProbe.status)" size="small">
            {{ aiProbe.status === 'ok' ? `✓ ${aiProbe.sample}` : (aiProbe.status === 'running' ? '验证中...' : '✗ 失败') }}
          </el-tag>
          <span v-if="aiProbe.error" class="err">{{ aiProbe.error }}</span>
        </div>
        <div class="hint">
          DeepSeek：约 ¥10 能玩一个月。
          <el-link href="https://platform.deepseek.com/api_keys" target="_blank" type="primary">
            创建 Key ↗
          </el-link>
        </div>
      </el-form-item>

      <el-form-item label="AI 模型（可选，留空 = 默认）">
        <el-input v-model="form.ai_model" placeholder="deepseek-chat" />
      </el-form-item>

      <!-- 仓库选择 -->
      <el-form-item label="当前仓库">
        <el-select
          v-model="form.repo"
          filterable
          allow-create
          default-first-option
          placeholder="选一个或手动输入 owner/name"
          style="width: 100%"
        >
          <el-option
            v-for="r in repos"
            :key="r.full_name"
            :label="r.full_name + (r.private ? ' 🔒' : '')"
            :value="r.full_name"
          >
            <span>{{ r.full_name }}</span>
            <el-tag v-if="r.private" size="small" type="info" style="margin-left: 8px">私有</el-tag>
          </el-option>
        </el-select>
        <div class="hint">
          填 GitHub token 并测试后，这里会自动列出你能访问的仓库。也可以直接打字搜或填新名字。
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="clear" type="danger" plain>清空凭据</el-button>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :disabled="!canSave" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.probe-result {
  margin-top: 6px; display: flex; align-items: center; gap: 8px;
}
.err { color: #ef4444; font-size: 12px; }
.hint { color: #6b7280; font-size: 12px; margin-top: 4px; }
</style>
