<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { actionsApi } from '../api/client'

const runs = ref([])
const workflows = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const [wfsResp, runsResp] = await Promise.all([
      actionsApi.workflows(),
      actionsApi.runs(undefined, 15),
    ])
    workflows.value = wfsResp.data.workflows || []
    runs.value = runsResp.data.runs || []
  } catch (e) {
    ElMessage.error('加载失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function statusType(r) {
  if (r.status !== 'completed') return 'warning'
  if (r.conclusion === 'success') return 'success'
  if (r.conclusion === 'failure') return 'danger'
  return 'info'
}

async function dispatch(wf) {
  try {
    await actionsApi.dispatch(wf.path.split('/').pop(), 'main', {})
    ElMessage.success('已触发')
    setTimeout(load, 1500)
  } catch (e) {
    ElMessage.error('触发失败：' + (e.response?.data?.detail || e.message))
  }
}

onMounted(load)
</script>

<template>
  <div class="runs-panel">
    <div class="bar">
      <el-button :icon="Refresh" size="small" @click="load">刷新</el-button>
    </div>

    <h4>工作流</h4>
    <el-table v-loading="loading" :data="workflows" size="small" empty-text="还没有 workflow">
      <el-table-column prop="name" label="名字" />
      <el-table-column prop="state" label="状态" width="80" />
      <el-table-column width="80">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="dispatch(row)">运行</el-button>
        </template>
      </el-table-column>
    </el-table>

    <h4 style="margin-top: 14px">最近运行</h4>
    <el-table :data="runs" size="small" empty-text="暂无运行">
      <el-table-column prop="name" label="名字" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row)" size="small">
            {{ row.status === 'completed' ? row.conclusion || '?' : row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="分支" prop="head_branch" width="100" />
      <el-table-column width="60">
        <template #default="{ row }">
          <el-link :href="row.html_url" target="_blank" type="primary">↗</el-link>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.runs-panel { padding: 8px 4px; }
.bar { margin-bottom: 8px; }
h4 { margin: 4px 0 6px; font-size: 13px; color: #6b7280; font-weight: 500; }
</style>
