<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useVaultStore } from '../stores/vault'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'unlocked'])

const vault = useVaultStore()
const password = ref('')
const trying = ref(false)

watch(
  () => props.modelValue,
  (v) => { if (v) password.value = '' }
)

async function submit() {
  if (!password.value) return ElMessage.warning('请输入主密码')
  trying.value = true
  try {
    await vault.unlock(password.value)
    ElMessage.success('解锁成功')
    emit('update:modelValue', false)
    emit('unlocked')
  } catch (e) {
    ElMessage.error(e.message)
    password.value = ''
  } finally {
    trying.value = false
  }
}

async function resetAll() {
  await vault.clear()
  ElMessage.warning('已清空所有凭据')
  emit('update:modelValue', false)
  location.reload()
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="解锁凭据保险箱"
    width="420px"
    :close-on-click-modal="false"
    :show-close="false"
  >
    <p style="color: #6b7280; font-size: 13px; margin-top: 0">
      检测到本地有加密的凭据，请输入主密码解锁。
    </p>

    <el-input
      v-model="password"
      type="password"
      show-password
      placeholder="主密码"
      size="large"
      @keyup.enter="submit"
      autofocus
    />

    <template #footer>
      <el-button type="danger" plain @click="resetAll">忘了 / 重置</el-button>
      <el-button type="primary" :loading="trying" @click="submit">解锁</el-button>
    </template>
  </el-dialog>
</template>
