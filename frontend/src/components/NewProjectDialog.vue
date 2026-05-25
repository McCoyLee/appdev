<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { templatesApi, projectsApi } from '../api/client'
import { useVaultStore } from '../stores/vault'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'created'])

const vault = useVaultStore()
const step = ref(1) // 1=选模板, 2=填信息, 3=进度
const templates = ref([])
const loadingTpls = ref(false)
const form = ref({
  template_id: 'static-site',
  name: '',
  description: '',
  private: false,
  mode: 'init', // 'create' = 自动建仓库（需 PAT 创建权限）; 'init' = 用已有空仓库
  existing_repo: '', // mode=init 时填的 owner/name
})
const progress = ref({
  running: false,
  steps: [],
  result: null,
  error: null,
})

const selectedTpl = computed(() =>
  templates.value.find((t) => t.id === form.value.template_id)
)

const ownerLogin = computed(() => vault.data?.repo?.split('/')?.[0] || 'YourGitHubName')

async function loadTemplates() {
  loadingTpls.value = true
  try {
    const { data } = await templatesApi.list()
    templates.value = data.templates || []
  } catch (e) {
    ElMessage.error('加载模板失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loadingTpls.value = false
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      step.value = 1
      progress.value = { running: false, steps: [], result: null, error: null }
      if (!templates.value.length) loadTemplates()
    }
  }
)

function next() {
  if (step.value === 1) {
    if (!form.value.template_id) return ElMessage.warning('请选一个模板')
    step.value = 2
    return
  }
  if (step.value === 2) {
    if (form.value.mode === 'create') {
      if (!/^[a-zA-Z0-9._-]+$/.test(form.value.name)) {
        return ElMessage.warning('仓库名只允许字母/数字/. _ -')
      }
      submit()
    } else {
      if (!/^[^/]+\/[^/]+$/.test(form.value.existing_repo || '')) {
        return ElMessage.warning('已有仓库格式应为 owner/name')
      }
      submitInit()
    }
  }
}

async function submit() {
  step.value = 3
  progress.value.running = true
  progress.value.steps = [{ label: '创建仓库', status: 'running' }]
  try {
    const { data } = await projectsApi.create({
      template_id: form.value.template_id,
      name: form.value.name,
      description: form.value.description,
      private: form.value.private,
    })
    progress.value.steps = (data.steps || []).map((s) => ({
      label: stepLabel(s.step),
      status: s.ok ? 'done' : 'fail',
      detail: s.error || s.repo || s.url || `${s.files || ''} 文件 / ${s.commit || ''}`,
    }))
    progress.value.result = data
    ElMessage.success('项目已创建')
  } catch (e) {
    progress.value.error = e.response?.data?.detail || e.message
    ElMessage.error('创建失败')
  } finally {
    progress.value.running = false
  }
}

async function submitInit() {
  step.value = 3
  progress.value.running = true
  progress.value.steps = [
    { label: '验证仓库', status: 'running' },
    { label: '推送模板内容', status: 'pending' },
    { label: '启用 GitHub Pages', status: 'pending' },
    { label: '放开分支策略', status: 'pending' },
  ]
  try {
    const { data } = await projectsApi.init({
      template_id: form.value.template_id,
      repo: form.value.existing_repo,
    })
    progress.value.steps = [
      { label: '验证仓库', status: 'done', detail: data.repo },
      { label: '推送模板内容', status: 'done', detail: `${data.files_pushed} 文件 / ${data.commit}` },
      {
        label: '启用 GitHub Pages',
        status: data.pages_enabled ? 'done' : 'skipped',
        detail: data.pages_url || (selectedTpl.value?.id !== 'static-site' ? '该模板无需 Pages' : '已启用或无权限'),
      },
      {
        label: '放开分支策略',
        status: data.branch_policy_open ? 'done' : 'skipped',
        detail: data.branch_policy_open ? '已放开' : '需 PAT 加 Environments R/W 才能自动；不影响推送',
      },
    ]
    progress.value.result = data
    ElMessage.success('模板推送完成')
  } catch (e) {
    progress.value.error = e.response?.data?.detail || e.message
    ElMessage.error('失败')
  } finally {
    progress.value.running = false
  }
}

function stepLabel(s) {
  return {
    create_repo: '创建仓库',
    push_template: '推送模板内容',
    enable_pages: '启用 GitHub Pages',
    open_branch_policy: '放开分支策略',
  }[s] || s
}

async function switchToRepo() {
  const repo = progress.value.result?.repo
  if (!repo) return
  await vault.update({ repo })
  emit('created', repo)
  emit('update:modelValue', false)
}

function backToStep1() {
  step.value = 1
  progress.value = { running: false, steps: [], result: null, error: null }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="(v) => emit('update:modelValue', v)"
    title="新建项目"
    width="640px"
    :close-on-click-modal="!progress.running"
  >
    <el-steps :active="step - 1" finish-status="success" simple style="margin-bottom: 20px">
      <el-step title="选模板" />
      <el-step title="填信息" />
      <el-step title="完成" />
    </el-steps>

    <!-- 步骤 1：选模板 -->
    <div v-if="step === 1" v-loading="loadingTpls" class="tpl-list">
      <div
        v-for="t in templates"
        :key="t.id"
        class="tpl-card"
        :class="{ active: form.template_id === t.id }"
        @click="form.template_id = t.id"
      >
        <div class="tpl-head">
          <h4>{{ t.name }}</h4>
          <el-tag v-if="form.template_id === t.id" type="primary" size="small">已选</el-tag>
        </div>
        <p class="desc">{{ t.description }}</p>
        <div class="tags">
          <el-tag v-for="tag in t.tags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
          <el-tag type="info" size="small" effect="plain">部署：{{ t.deploy_target }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 步骤 2：填信息 -->
    <div v-if="step === 2">
      <el-alert
        v-if="selectedTpl?.required_secrets?.length"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      >
        <template #title>这个模板需要密钥</template>
        <div>
          创建后去【密码本】tab 添加：
          <code v-for="s in selectedTpl.required_secrets" :key="s.name" style="margin-right: 6px">
            {{ s.name }}
          </code>
        </div>
      </el-alert>

      <el-form label-width="100px" label-position="top">
        <el-form-item>
          <template #label>
            <span>创建方式</span>
          </template>
          <el-radio-group v-model="form.mode">
            <el-radio value="init">
              我已经建好空仓库（推荐）
            </el-radio>
            <el-radio value="create">
              帮我自动建仓库（需 PAT 加 Repository creation 权限）
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- mode = init: 选已有仓库 -->
        <template v-if="form.mode === 'init'">
          <el-form-item label="已有仓库">
            <el-input
              v-model="form.existing_repo"
              :placeholder="`${ownerLogin}/your-new-repo`"
            />
            <div class="hint">
              先去 <el-link href="https://github.com/new" target="_blank" type="primary">github.com/new</el-link> 创建一个空仓库（勾选 "Add a README" 让 main 分支存在），然后填这里。
            </div>
          </el-form-item>
        </template>

        <!-- mode = create -->
        <template v-else>
          <el-form-item label="项目名">
            <el-input v-model="form.name" placeholder="my-website" />
            <div class="hint">仓库将创建为 <code>{{ ownerLogin }}/{{ form.name || '...' }}</code></div>
          </el-form-item>
          <el-form-item label="描述（可选）">
            <el-input v-model="form.description" placeholder="一句话说明" />
          </el-form-item>
          <el-form-item label="可见性">
            <el-radio-group v-model="form.private">
              <el-radio :value="false">公开</el-radio>
              <el-radio :value="true">私有</el-radio>
            </el-radio-group>
          </el-form-item>
        </template>
      </el-form>
    </div>

    <!-- 步骤 3：进度 -->
    <div v-if="step === 3">
      <div v-for="(s, i) in progress.steps" :key="i" class="prog-row">
        <el-icon v-if="s.status === 'running'" class="rotate"><Loading /></el-icon>
        <el-icon v-else-if="s.status === 'done'" style="color: #10b981"><Check /></el-icon>
        <el-icon v-else-if="s.status === 'fail'" style="color: #ef4444"><Close /></el-icon>
        <el-icon v-else-if="s.status === 'skipped'" style="color: #9ca3af"><Minus /></el-icon>
        <el-icon v-else style="color: #d1d5db"><MoreFilled /></el-icon>
        <span class="prog-label">{{ s.label }}</span>
        <span v-if="s.detail" class="prog-detail">{{ s.detail }}</span>
      </div>

      <el-alert
        v-if="progress.error"
        type="error"
        :closable="false"
        show-icon
        style="margin-top: 16px"
      >
        <template #title>失败</template>
        <pre class="err">{{ progress.error }}</pre>
      </el-alert>

      <el-alert
        v-if="progress.result && !progress.running"
        type="success"
        :closable="false"
        show-icon
        style="margin-top: 16px"
      >
        <template #title>搞定！</template>
        <div>
          仓库：<el-link :href="progress.result.html_url" target="_blank" type="primary">{{ progress.result.repo }}</el-link>
          <span v-if="progress.result.pages_url">
            ｜ Pages：<el-link :href="progress.result.pages_url" target="_blank" type="primary">{{ progress.result.pages_url }}</el-link>
          </span>
        </div>
      </el-alert>
    </div>

    <template #footer>
      <el-button v-if="step === 2" @click="step = 1">上一步</el-button>
      <el-button v-if="step === 3 && progress.error" @click="backToStep1">重来</el-button>
      <el-button @click="emit('update:modelValue', false)" :disabled="progress.running">
        {{ progress.running ? '执行中...' : '取消' }}
      </el-button>
      <el-button
        v-if="step < 3"
        type="primary"
        @click="next"
      >
        {{ step === 1 ? '下一步' : (form.mode === 'create' ? '创建' : '开干') }}
      </el-button>
      <el-button
        v-if="step === 3 && progress.result && !progress.running"
        type="primary"
        @click="switchToRepo"
      >
        切到这个项目
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.tpl-list { display: flex; flex-direction: column; gap: 10px; max-height: 50vh; overflow: auto; }
.tpl-card {
  border: 2px solid #e5e7eb; border-radius: 8px;
  padding: 12px 14px; cursor: pointer; transition: all 0.15s;
}
.tpl-card:hover { border-color: #93c5fd; background: #f0f9ff; }
.tpl-card.active { border-color: #2563eb; background: #eff6ff; }
.tpl-head { display: flex; align-items: center; justify-content: space-between; }
.tpl-head h4 { margin: 0; font-size: 15px; }
.desc { color: #4b5563; margin: 6px 0; font-size: 13px; line-height: 1.6; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; }
.hint { color: #6b7280; font-size: 12px; margin-top: 4px; }
.hint code { background: #f3f4f6; padding: 1px 6px; border-radius: 4px; }
.prog-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 0; border-bottom: 1px solid #f3f4f6;
}
.prog-label { flex: 0 0 130px; font-size: 13px; }
.prog-detail { color: #6b7280; font-size: 12px; font-family: ui-monospace, monospace; }
.err { font-size: 12px; white-space: pre-wrap; margin: 0; }
.rotate { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
</style>
