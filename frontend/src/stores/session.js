import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSessionStore = defineStore('session', () => {
  const repo = ref(null)
  const user = ref(null)
  const messages = ref([])
  const usage = ref({ prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 })
  // M1: 跟踪 AI 当前在哪个 ai/* 分支干活
  const currentBranch = ref(null)
  // 用户最近一次「就这版」之后用于回滚或显示用
  const lastAdopted = ref(null)

  function reset() {
    messages.value = []
    usage.value = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
    currentBranch.value = null
  }

  function addUsage(u) {
    for (const k of Object.keys(usage.value)) {
      usage.value[k] += u?.[k] || 0
    }
  }

  return { repo, user, messages, usage, currentBranch, lastAdopted, reset, addUsage }
})
