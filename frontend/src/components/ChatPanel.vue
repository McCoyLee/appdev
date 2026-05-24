<script setup>
import { ref, nextTick, computed } from 'vue'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'
import PlanCard from './PlanCard.vue'
import { streamChat } from '../api/chat'
import { useSessionStore } from '../stores/session'

const sess = useSessionStore()
const input = ref('')
const sending = ref(false)
const scroller = ref(null)

const rendered = computed(() => {
  return sess.messages.map((m) => {
    if (m.role === 'user') return { kind: 'user', text: m.content }
    if (m.role === 'assistant') {
      return { kind: 'assistant', text: m.content, tools: m.tool_calls || [] }
    }
    if (m.role === 'tool_event') {
      // propose_plan 工具的结果用专门的 PlanCard 渲染
      if (m.name === 'propose_plan' && m.ok && m.result?.plan) {
        return { kind: 'plan', plan: m.result.plan, id: m.tool_call_id || `plan-${m.ts || Date.now()}` }
      }
      return { kind: 'tool', name: m.name, args: m.args, result: m.result, ok: m.ok }
    }
  })
})

function onPlanConfirm(payload) {
  const lines = payload.steps.map((s, i) => `${i + 1}. ${s.title}`)
  const msg = `已确认计划，请按以下顺序执行：\n${lines.join('\n')}`
  input.value = msg
  send()
}

async function scrollDown() {
  await nextTick()
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}

function renderMd(text) {
  return marked.parse(text || '', { breaks: true })
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return
  input.value = ''
  sess.messages.push({ role: 'user', content: text })

  // 给 agent 的 history 只保留 user/assistant 角色的对话（不含 tool_event UI 卡片）
  const apiHistory = sess.messages
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => ({ role: m.role, content: m.content }))

  sending.value = true
  let currentAssistant = null
  await scrollDown()

  try {
    await streamChat({
      messages: apiHistory,
      onEvent: async ({ type, data }) => {
        if (type === 'assistant_text') {
          if (!data.content?.trim()) return
          currentAssistant = { role: 'assistant', content: data.content }
          sess.messages.push(currentAssistant)
        } else if (type === 'tool_call') {
          sess.messages.push({
            role: 'tool_event',
            name: data.name,
            args: data.arguments,
            tool_call_id: data.id,
            result: null,
            ok: null,
          })
        } else if (type === 'tool_result') {
          for (let i = sess.messages.length - 1; i >= 0; i--) {
            const m = sess.messages[i]
            if (m.role === 'tool_event' && m.name === data.name && m.result === null) {
              m.result = data.payload.result ?? data.payload.error
              m.ok = data.payload.ok
              break
            }
          }
          // 跟踪 AI 当前在哪个 ai/* 分支干活
          if (data.payload?.ok && data.name === 'ensure_branch') {
            const br = data.payload.result?.branch
            if (br?.startsWith('ai/')) sess.currentBranch = br
          }
          if (data.payload?.ok && data.name === 'write_file') {
            for (let i = sess.messages.length - 1; i >= 0; i--) {
              const m = sess.messages[i]
              if (m.role === 'tool_event' && m.name === 'write_file' && m.result !== null) {
                const br = m.args?.branch
                if (br?.startsWith('ai/')) sess.currentBranch = br
                break
              }
            }
          }
        } else if (type === 'preview_triggered') {
          ElMessage.success(`正在部署预览 (${data.branch})`)
        } else if (type === 'preview_error') {
          ElMessage.warning('预览部署触发失败：' + data.message)
        } else if (type === 'usage') {
          sess.addUsage(data)
        } else if (type === 'error') {
          ElMessage.error(data.message || '出错')
        }
        await scrollDown()
      },
    })
  } catch (e) {
    ElMessage.error('对话失败：' + e.message)
  } finally {
    sending.value = false
    scrollDown()
  }
}
</script>

<template>
  <div class="chat-panel">
    <div class="messages" ref="scroller">
      <el-empty v-if="!rendered.length" description="对 AI 说一句话，让它改你的仓库" />
      <div v-for="(m, i) in rendered" :key="i" class="msg" :class="m.kind">
        <div v-if="m.kind === 'user'" class="bubble user-bubble">{{ m.text }}</div>
        <div v-else-if="m.kind === 'assistant'" class="bubble assistant-bubble" v-html="renderMd(m.text)"></div>
        <PlanCard
          v-else-if="m.kind === 'plan'"
          :plan="m.plan"
          :tool-call-id="m.id"
          @confirm="onPlanConfirm"
          style="width: 100%"
        />
        <div v-else-if="m.kind === 'tool'" class="tool-card" :class="{ ok: m.ok, fail: m.ok === false }">
          <div class="tool-head">
            <el-icon><Tools /></el-icon>
            <code>{{ m.name }}</code>
            <el-tag v-if="m.ok === true" size="small" type="success">ok</el-tag>
            <el-tag v-else-if="m.ok === false" size="small" type="danger">fail</el-tag>
            <el-tag v-else size="small" type="info">运行中</el-tag>
          </div>
          <div class="tool-body">
            <pre class="args">{{ JSON.stringify(m.args, null, 2) }}</pre>
            <pre v-if="m.result !== null" class="result">{{ typeof m.result === 'string' ? m.result : JSON.stringify(m.result, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>
    <div class="footer">
      <div class="usage" v-if="sess.usage.total_tokens">
        累计 tokens: {{ sess.usage.total_tokens }}
        <span class="muted">(prompt {{ sess.usage.prompt_tokens }} / completion {{ sess.usage.completion_tokens }})</span>
      </div>
      <el-input
        v-model="input"
        type="textarea"
        :rows="3"
        :disabled="sending"
        placeholder="比如：把 README 改成中文 / 在 src 目录新建一个 index.html"
        @keydown.enter.exact.prevent="send"
      />
      <div class="actions">
        <el-button @click="sess.reset()" :disabled="sending">清空对话</el-button>
        <el-button type="primary" :loading="sending" @click="send">发送 (Enter)</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-panel { display: flex; flex-direction: column; height: 100%; }
.messages { flex: 1; overflow: auto; padding: 16px; }
.msg { margin-bottom: 14px; display: flex; }
.msg.user { justify-content: flex-end; }
.bubble {
  max-width: 80%; padding: 10px 14px; border-radius: 10px;
  line-height: 1.6; white-space: pre-wrap; word-break: break-word;
}
.user-bubble { background: #2563eb; color: white; }
.assistant-bubble { background: #f3f4f6; color: #111827; }
.assistant-bubble :deep(p) { margin: 4px 0; }
.assistant-bubble :deep(pre) { background: #1f2937; color: #f3f4f6; padding: 8px; border-radius: 6px; overflow-x: auto; }
.assistant-bubble :deep(code) { font-family: ui-monospace, monospace; }
.assistant-bubble :deep(table) { border-collapse: collapse; }
.assistant-bubble :deep(th), .assistant-bubble :deep(td) { border: 1px solid #d1d5db; padding: 4px 8px; }

.tool-card {
  background: #fafbfc; border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 8px 12px; width: 100%; font-size: 12px;
}
.tool-card.ok { border-left: 3px solid #10b981; }
.tool-card.fail { border-left: 3px solid #ef4444; }
.tool-head { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.tool-head code { background: none; color: #2563eb; font-weight: 600; }
.tool-body pre {
  margin: 4px 0 0; padding: 6px 8px; background: #f3f4f6;
  border-radius: 4px; max-height: 160px; overflow: auto; font-size: 11px;
}
.tool-body .result { background: #ecfdf5; }

.footer { border-top: 1px solid #e5e7eb; padding: 10px 14px; }
.usage { font-size: 12px; color: #6b7280; margin-bottom: 6px; }
.muted { color: #9ca3af; }
.actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px; }
</style>
