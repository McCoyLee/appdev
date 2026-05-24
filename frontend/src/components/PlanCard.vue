<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  plan: { type: Object, required: true },
  toolCallId: { type: String, required: true },
})
const emit = defineEmits(['confirm'])

// 用户可勾选/调整的 step 状态
const steps = ref(
  (props.plan.steps || []).map((s) => ({
    ...s,
    enabled: true,
  }))
)
const confirmed = ref(false)

const enabledCount = computed(() => steps.value.filter((s) => s.enabled).length)

function toggleStep(i) {
  steps.value[i].enabled = !steps.value[i].enabled
}

function confirm() {
  const selected = steps.value.filter((s) => s.enabled)
  if (!selected.length) return
  confirmed.value = true
  emit('confirm', {
    steps: selected,
    rationale: props.plan.rationale,
  })
}
</script>

<template>
  <div class="plan-card">
    <div class="plan-head">
      <el-icon><Memo /></el-icon>
      <span>AI 提议的计划</span>
      <el-tag size="small" type="info">{{ enabledCount }} / {{ steps.length }} 步</el-tag>
    </div>

    <p v-if="plan.rationale" class="rationale">{{ plan.rationale }}</p>

    <div class="step-list">
      <div
        v-for="(s, i) in steps"
        :key="i"
        class="step-row"
        :class="{ disabled: !s.enabled, done: confirmed && s.enabled }"
      >
        <el-checkbox
          :model-value="s.enabled"
          @update:model-value="toggleStep(i)"
          :disabled="confirmed"
        />
        <div class="step-body">
          <div class="step-title">{{ i + 1 }}. {{ s.title }}</div>
          <div v-if="s.files?.length" class="step-files">
            <code v-for="f in s.files" :key="f">{{ f }}</code>
          </div>
          <div v-if="s.details" class="step-details">{{ s.details }}</div>
        </div>
      </div>
    </div>

    <div v-if="!confirmed" class="actions">
      <el-button
        type="primary"
        size="default"
        :disabled="!enabledCount"
        @click="confirm"
      >
        ✓&nbsp;按此执行（{{ enabledCount }} 步）
      </el-button>
      <span class="hint">想调整？取消勾选不想要的步骤</span>
    </div>
    <div v-else class="confirmed-tag">
      <el-tag type="success" size="small">已确认，AI 正在执行</el-tag>
    </div>
  </div>
</template>

<style scoped>
.plan-card {
  border: 2px solid #2563eb;
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 60%);
  border-radius: 8px;
  padding: 14px 16px;
  margin: 6px 0;
}
.plan-head {
  display: flex; align-items: center; gap: 8px;
  font-weight: 600; font-size: 14px;
  color: #1e40af;
}
.rationale {
  color: #4b5563;
  font-size: 13px;
  margin: 8px 0;
  padding: 6px 10px;
  background: #f9fafb;
  border-left: 3px solid #93c5fd;
  border-radius: 4px;
}
.step-list { margin: 10px 0; }
.step-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 6px;
  border-radius: 6px;
  transition: all 0.15s;
}
.step-row:hover { background: #f3f4f6; }
.step-row.disabled { opacity: 0.45; }
.step-row.done { background: #ecfdf5; }
.step-body { flex: 1; }
.step-title { font-size: 13px; font-weight: 500; }
.step-files {
  margin-top: 4px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.step-files code {
  background: #f3f4f6;
  color: #2563eb;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-family: ui-monospace, monospace;
}
.step-details {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
  line-height: 1.6;
}
.actions {
  display: flex; align-items: center; gap: 12px;
  margin-top: 8px; padding-top: 8px;
  border-top: 1px solid #e5e7eb;
}
.hint { color: #9ca3af; font-size: 12px; }
.confirmed-tag { margin-top: 8px; }
</style>
