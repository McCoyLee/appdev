<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { previewApi, branchesApi } from '../api/client'
import { useSessionStore } from '../stores/session'

const sess = useSessionStore()
const status = ref(null)
const polling = ref(false)
const adopting = ref(false)
let timer = null

const activeBranch = computed(() => sess.currentBranch || sess.repo?.default_branch || 'main')
const isAiBranch = computed(() => activeBranch.value?.startsWith('ai/'))

const runStatusText = computed(() => {
  const r = status.value?.latest_run
  if (!r) return '尚未部署'
  if (r.status !== 'completed') return '部署中…'
  if (r.conclusion === 'success') return '已上线'
  if (r.conclusion === 'failure') return '部署失败'
  return r.conclusion || r.status
})

const runStatusType = computed(() => {
  const r = status.value?.latest_run
  if (!r) return 'info'
  if (r.status !== 'completed') return 'warning'
  if (r.conclusion === 'success') return 'success'
  if (r.conclusion === 'failure') return 'danger'
  return 'info'
})

const iframeUrl = computed(() => {
  if (!status.value?.deployment_url) return null
  // 缓存击穿
  return status.value.deployment_url + (status.value.deployment_url.includes('?') ? '&' : '?') + 't=' + Date.now()
})

async function refresh() {
  if (!activeBranch.value) return
  try {
    const { data } = await previewApi.status(activeBranch.value)
    status.value = data
  } catch (e) {
    // 静默
  }
}

async function triggerPreview() {
  if (!isAiBranch.value) return
  try {
    await previewApi.trigger(activeBranch.value)
    ElMessage.success('已触发部署')
    await refresh()
  } catch (e) {
    ElMessage.error('触发失败：' + (e.response?.data?.detail || e.message))
  }
}

async function adopt() {
  if (!isAiBranch.value) return
  try {
    await ElMessageBox.confirm(
      '把这一版采纳到 main，并删除 AI 分支。下次预览会更新成 main 的内容。',
      '采纳这一版',
      { confirmButtonText: '就这版', cancelButtonText: '再想想', type: 'success' }
    )
  } catch {
    return
  }
  adopting.value = true
  try {
    const { data } = await branchesApi.adopt(activeBranch.value, sess.repo?.default_branch || 'main')
    sess.lastAdopted = data.adopted_from
    sess.currentBranch = null
    ElMessage.success(`已采纳 ${data.adopted_from} → ${data.target}`)
    await refresh()
  } catch (e) {
    ElMessage.error('采纳失败：' + (e.response?.data?.detail || e.message))
  } finally {
    adopting.value = false
  }
}

async function discard() {
  if (!isAiBranch.value) return
  try {
    await ElMessageBox.confirm(
      '丢弃这一版所有改动？AI 分支会被删除，预览也会失效。',
      '丢弃这一版',
      { confirmButtonText: '丢弃', cancelButtonText: '不丢', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await branchesApi.discard(activeBranch.value)
    sess.currentBranch = null
    ElMessage.success('已丢弃')
    await refresh()
  } catch (e) {
    ElMessage.error('丢弃失败：' + (e.response?.data?.detail || e.message))
  }
}

const fixingPolicy = ref(false)
async function fixBranchPolicy() {
  fixingPolicy.value = true
  try {
    await previewApi.setupEnvironment()
    ElMessage.success('已放开 deployment branch policy，再次重新部署试试')
    await refresh()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally {
    fixingPolicy.value = false
  }
}

function startPolling() {
  stopPolling()
  polling.value = true
  timer = setInterval(refresh, 4000)
}

function stopPolling() {
  if (timer) clearInterval(timer)
  timer = null
  polling.value = false
}

watch(() => activeBranch.value, refresh)
// 部署进行中持续轮询
watch(
  () => status.value?.latest_run?.status,
  (s) => {
    if (s && s !== 'completed') startPolling()
    else stopPolling()
  }
)

onMounted(refresh)
onUnmounted(stopPolling)
</script>

<template>
  <div class="preview-panel">
    <div class="head">
      <div class="row branch-row">
        <el-tag v-if="isAiBranch" type="warning" effect="dark" size="default" class="branch-tag">
          <el-icon><Promotion /></el-icon>
          <span class="branch-name">{{ activeBranch }}</span>
        </el-tag>
        <el-tag v-else type="info" effect="dark" size="default" class="branch-tag">
          <el-icon><Promotion /></el-icon>
          <span class="branch-name">{{ activeBranch }} (生产)</span>
        </el-tag>
        <el-tag :type="runStatusType" size="default" effect="light">
          {{ runStatusText }}
        </el-tag>
      </div>

      <div class="row tool-row">
        <el-button v-if="isAiBranch" size="small" link @click="triggerPreview">
          <el-icon><Refresh /></el-icon>&nbsp;重新部署
        </el-button>
        <el-button size="small" link @click="refresh">
          <el-icon><Refresh /></el-icon>&nbsp;刷新
        </el-button>
      </div>

      <div v-if="isAiBranch" class="row action-row">
        <el-button type="success" size="large" :loading="adopting" @click="adopt" class="big-btn">
          ✓&nbsp; 就这版
        </el-button>
        <el-button type="danger" size="large" plain @click="discard" class="big-btn">
          ✗&nbsp; 丢弃
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="status && !status.pages_enabled"
      type="warning"
      :closable="false"
      show-icon
      class="hint"
    >
      <template #title>GitHub Pages 还没启用</template>
      <div>
        去仓库 Settings → Pages → Source 选 <b>GitHub Actions</b>。
        <el-link :href="`${sess.repo?.html_url}/settings/pages`" target="_blank" type="primary">
          打开设置 ↗
        </el-link>
      </div>
    </el-alert>

    <el-alert
      v-if="status?.latest_run?.conclusion === 'failure' && isAiBranch"
      type="error"
      :closable="false"
      show-icon
      class="hint"
    >
      <template #title>部署失败</template>
      <div>
        常见原因：github-pages 环境的 deployment branch policy 限制只允许 main。
        <div style="margin-top: 6px; display: flex; gap: 8px; align-items: center">
          <el-button
            type="warning"
            size="small"
            :loading="fixingPolicy"
            @click="fixBranchPolicy"
          >
            一键放开限制
          </el-button>
          <el-link
            :href="`${sess.repo?.html_url}/settings/environments`"
            target="_blank"
            type="primary"
          >
            手动打开环境设置 ↗
          </el-link>
        </div>
      </div>
    </el-alert>

    <div class="iframe-wrap">
      <iframe v-if="iframeUrl" :src="iframeUrl" :key="iframeUrl" />
      <el-empty v-else description="部署完成后这里会显示预览" :image-size="80" />
    </div>

    <div v-if="status?.latest_run" class="footer">
      <el-link :href="status.latest_run.html_url" target="_blank" type="info">
        查看构建日志 ↗
      </el-link>
      <span class="ts">{{ new Date(status.latest_run.updated_at).toLocaleTimeString() }}</span>
    </div>
  </div>
</template>

<style scoped>
.preview-panel {
  display: flex; flex-direction: column; height: 100%;
  padding: 8px 4px; gap: 6px; overflow: auto;
}
.head { display: flex; flex-direction: column; gap: 6px; }
.row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.branch-row .branch-tag {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
.branch-name { margin-left: 4px; }
.tool-row { color: #6b7280; }
.action-row { padding-top: 4px; }
.big-btn {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
}
.hint { margin: 4px 0; }
.iframe-wrap {
  flex: 1; border: 1px solid #e5e7eb; border-radius: 6px;
  overflow: hidden; background: #fafafa; min-height: 320px;
  display: flex; align-items: center; justify-content: center;
}
.iframe-wrap iframe { width: 100%; height: 100%; border: 0; background: white; }
.footer {
  display: flex; justify-content: space-between; align-items: center;
  padding: 4px 6px; font-size: 12px; color: #6b7280;
}
.ts { color: #9ca3af; font-family: ui-monospace, monospace; }
</style>
