<script setup>
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useVaultStore } from '../stores/vault'

const props = defineProps({
  modelValue: Boolean,
  runId: { type: [Number, String], default: null },
  runName: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const vault = useVaultStore()
const jobs = ref({}) // job_id -> { name, status, conclusion, logs: [] }
const runStatus = ref({ status: '', conclusion: null })
const streaming = ref(false)
const scroller = ref(null)
let controller = null

async function scrollDown() {
  await nextTick()
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}

async function startStream() {
  if (!props.runId) return
  jobs.value = {}
  runStatus.value = { status: 'starting', conclusion: null }
  streaming.value = true
  controller = new AbortController()

  try {
    const url = '/api/runs/' + props.runId + '/stream'
    const resp = await fetch(url, {
      headers: { Accept: 'text/event-stream', ...vault.authHeaders() },
      signal: controller.signal,
    })
    if (!resp.ok) {
      throw new Error(`stream ${resp.status}`)
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, idx).replace(/\r$/, '')
        buffer = buffer.slice(idx + 1)
        if (!line) { currentEvent = null; continue }
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          const raw = line.slice(5).trim()
          let data
          try { data = JSON.parse(raw) } catch { data = raw }
          handleEvent(currentEvent, data)
          await scrollDown()
        }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      ElMessage.warning('日志流断开：' + e.message)
    }
  } finally {
    streaming.value = false
  }
}

function handleEvent(type, data) {
  if (type === 'status') {
    runStatus.value = { status: data.status, conclusion: data.conclusion }
  } else if (type === 'log') {
    const jid = data.job_id
    if (!jobs.value[jid]) {
      jobs.value[jid] = {
        name: data.job_name,
        status: data.job_status,
        conclusion: data.job_conclusion,
        text: '',
      }
    }
    jobs.value[jid].status = data.job_status
    jobs.value[jid].conclusion = data.job_conclusion
    jobs.value[jid].text += data.chunk
  } else if (type === 'done') {
    runStatus.value = { status: 'completed', conclusion: data.conclusion }
  } else if (type === 'error' || type === 'timeout') {
    ElMessage.warning(data.message || 'log stream error')
  }
}

function stop() {
  if (controller) controller.abort()
}

watch(
  () => props.modelValue,
  (v) => {
    if (v && props.runId) {
      startStream()
    } else {
      stop()
    }
  }
)

onUnmounted(stop)

function jobStatusColor(j) {
  if (j.conclusion === 'success') return 'success'
  if (j.conclusion === 'failure') return 'danger'
  if (j.status === 'in_progress') return 'warning'
  return 'info'
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="(v) => emit('update:modelValue', v)"
    :title="`Workflow 日志 · ${runName}`"
    width="80%"
    top="5vh"
  >
    <div class="run-status">
      <el-tag
        :type="runStatus.conclusion === 'success' ? 'success' :
               runStatus.conclusion === 'failure' ? 'danger' :
               runStatus.status === 'completed' ? 'info' : 'warning'"
        size="default"
      >
        {{ runStatus.status === 'completed' ? (runStatus.conclusion || '?') : runStatus.status }}
      </el-tag>
      <el-tag v-if="streaming" type="warning" size="small">实时拉取中</el-tag>
    </div>

    <div ref="scroller" class="logs-pane">
      <el-empty v-if="!Object.keys(jobs).length" description="等待日志..." :image-size="60" />
      <div v-for="(j, jid) in jobs" :key="jid" class="job-block">
        <div class="job-head">
          <el-tag :type="jobStatusColor(j)" size="small">
            {{ j.conclusion || j.status }}
          </el-tag>
          <span class="job-name">{{ j.name }}</span>
        </div>
        <pre class="log-text">{{ j.text }}</pre>
      </div>
    </div>

    <template #footer>
      <el-button v-if="streaming" @click="stop">停止拉取</el-button>
      <el-button @click="emit('update:modelValue', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.run-status { display: flex; gap: 8px; margin-bottom: 8px; }
.logs-pane {
  background: #0f172a; color: #e2e8f0;
  border-radius: 6px; padding: 12px;
  height: 60vh; overflow: auto;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 12px;
}
.job-block { margin-bottom: 16px; }
.job-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.job-name { color: #93c5fd; font-weight: 600; }
.log-text {
  margin: 0; white-space: pre-wrap; word-break: break-word;
  background: rgba(255,255,255,0.04); padding: 8px;
  border-radius: 4px; line-height: 1.5;
}
</style>
