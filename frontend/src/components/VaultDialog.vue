<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
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

watch(
  () => props.modelValue,
  (v) => {
    if (v) form.value = { ...form.value, ...vault.data }
  }
)

function save() {
  if (!form.value.github_token.trim()) return ElMessage.warning('请填 GitHub token')
  if (!form.value.ai_key.trim()) return ElMessage.warning('请填 AI key')
  if (!/^[^/]+\/[^/]+$/.test(form.value.repo || '')) return ElMessage.warning('repo 格式应为 owner/name')
  vault.update({ ...form.value })
  ElMessage.success('已保存（浏览器本地）')
  emit('update:modelValue', false)
  emit('saved')
}

function clear() {
  vault.clear()
  ElMessage.success('已清空，刷新页面')
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="(v) => emit('update:modelValue', v)"
    title="凭据配置"
    width="540px"
  >
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
      凭据保存在你浏览器的 localStorage 里（明文）。本平台后端不存储。
      下面三项填了之后，每次请求会自动带上 → 不再依赖 .env。
    </el-alert>

    <el-form label-width="120px" label-position="top">
      <el-form-item label="GitHub Token">
        <el-input
          v-model="form.github_token"
          type="password"
          show-password
          placeholder="fine-grained PAT，权限至少 Contents/Pull requests/Actions/Secrets R/W"
        />
        <div class="hint">
          去
          <el-link href="https://github.com/settings/personal-access-tokens/new" target="_blank" type="primary">
            github.com/settings/personal-access-tokens/new
          </el-link>
          创建
        </div>
      </el-form-item>

      <el-form-item label="AI Provider">
        <el-radio-group v-model="form.ai_provider">
          <el-radio value="deepseek">DeepSeek（推荐）</el-radio>
          <el-radio value="claude" disabled>Claude（暂未启用）</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="AI Key">
        <el-input
          v-model="form.ai_key"
          type="password"
          show-password
          placeholder="DeepSeek 的 sk-... 开头的 key"
        />
        <div class="hint">
          去
          <el-link href="https://platform.deepseek.com/api_keys" target="_blank" type="primary">
            platform.deepseek.com/api_keys
          </el-link>
          创建（约 ¥10 能玩一个月）
        </div>
      </el-form-item>

      <el-form-item label="AI 模型（可选）">
        <el-input v-model="form.ai_model" placeholder="留空 = deepseek-chat" />
      </el-form-item>

      <el-form-item label="仓库（owner/name）">
        <el-input v-model="form.repo" placeholder="如 McCoyLee/my-website" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="clear" type="danger" plain>清空凭据</el-button>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint { font-size: 12px; color: #6b7280; margin-top: 4px; }
</style>
