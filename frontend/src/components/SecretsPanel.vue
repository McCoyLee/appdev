<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Delete } from '@element-plus/icons-vue'
import { secretsApi } from '../api/client'

const secrets = ref([])
const loading = ref(false)
const dialog = ref(false)
const form = ref({ name: '', value: '' })

async function load() {
  loading.value = true
  try {
    const { data } = await secretsApi.list()
    secrets.value = data.secrets || []
  } catch (e) {
    ElMessage.error('加载失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!/^[A-Z_][A-Z0-9_]*$/.test(form.value.name)) {
    return ElMessage.warning('名字必须为大写字母 + 下划线（如 MY_API_KEY）')
  }
  try {
    await secretsApi.set(form.value.name, form.value.value)
    ElMessage.success('已保存')
    dialog.value = false
    form.value = { name: '', value: '' }
    await load()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  }
}

async function remove(name) {
  await ElMessageBox.confirm(`确定删除 ${name}？`, '警告', { type: 'warning' })
  try {
    await secretsApi.remove(name)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
  }
}

onMounted(load)
</script>

<template>
  <div class="secrets-panel">
    <div class="bar">
      <el-button type="primary" :icon="Plus" size="small" @click="dialog = true">添加密码</el-button>
      <el-button :icon="Refresh" size="small" @click="load">刷新</el-button>
    </div>
    <el-alert type="info" :closable="false" show-icon style="margin: 8px 0">
      密钥会加密存到 GitHub 仓库的 Secrets，连 AI 都看不到值，只知道名字。
    </el-alert>
    <el-table v-loading="loading" :data="secrets" size="small" empty-text="还没添加密码">
      <el-table-column label="名字" prop="name">
        <template #default="{ row }">
          <el-tag size="small">🔒 {{ row.name }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="160">
        <template #default="{ row }">
          <span class="muted">{{ new Date(row.updated_at).toLocaleString() }}</span>
        </template>
      </el-table-column>
      <el-table-column width="60">
        <template #default="{ row }">
          <el-button :icon="Delete" type="danger" link size="small" @click="remove(row.name)" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" title="添加 / 更新密钥" width="420px">
      <el-form label-width="80px">
        <el-form-item label="名字">
          <el-input v-model="form.name" placeholder="如 OPENAI_API_KEY" />
        </el-form-item>
        <el-form-item label="值">
          <el-input v-model="form.value" type="password" show-password placeholder="粘贴密钥" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.secrets-panel { padding: 8px 4px; }
.bar { display: flex; gap: 8px; }
.muted { color: #6b7280; font-size: 12px; }
</style>
