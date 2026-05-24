<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Top } from '@element-plus/icons-vue'
import { repoApi } from '../api/client'

const entries = ref([])
const loading = ref(false)
const currentPath = ref('')
const fileContent = ref(null)
const fileLoading = ref(false)
const pathSegments = ref([])

async function loadDir(path = '') {
  loading.value = true
  try {
    const { data } = await repoApi.tree(path)
    entries.value = (data.entries || []).sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    currentPath.value = path
    pathSegments.value = path ? path.split('/') : []
    fileContent.value = null
  } catch (e) {
    ElMessage.error('加载失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function onClick(entry) {
  if (entry.type === 'dir') {
    await loadDir(entry.path)
  } else {
    fileLoading.value = true
    try {
      const { data } = await repoApi.file(entry.path)
      fileContent.value = data
    } catch (e) {
      ElMessage.error('读取失败：' + (e.response?.data?.detail || e.message))
    } finally {
      fileLoading.value = false
    }
  }
}

function goUp() {
  if (!currentPath.value) return
  const parts = currentPath.value.split('/')
  parts.pop()
  loadDir(parts.join('/'))
}

function goSegment(idx) {
  loadDir(pathSegments.value.slice(0, idx + 1).join('/'))
}

onMounted(() => loadDir(''))
</script>

<template>
  <div class="repo-tree">
    <div class="path-bar">
      <el-button size="small" :icon="Refresh" @click="loadDir(currentPath)" />
      <el-button size="small" :icon="Top" :disabled="!currentPath" @click="goUp">上层</el-button>
      <el-breadcrumb separator="/">
        <el-breadcrumb-item @click.prevent="loadDir('')"><a href="#">/</a></el-breadcrumb-item>
        <el-breadcrumb-item v-for="(seg, i) in pathSegments" :key="i">
          <a href="#" @click.prevent="goSegment(i)">{{ seg }}</a>
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div v-loading="loading" class="entries">
      <div v-for="e in entries" :key="e.path" class="entry" @click="onClick(e)">
        <el-icon><FolderOpened v-if="e.type === 'dir'" /><Document v-else /></el-icon>
        <span class="name">{{ e.name }}</span>
        <span class="size" v-if="e.type === 'file'">{{ e.size }} B</span>
      </div>
      <div v-if="!entries.length && !loading" class="empty">空目录</div>
    </div>

    <el-dialog v-model="fileContent" :title="fileContent?.path" width="80%" v-if="fileContent">
      <pre class="file-preview">{{ fileContent.content }}</pre>
    </el-dialog>
  </div>
</template>

<style scoped>
.repo-tree { padding: 8px 0; }
.path-bar { display: flex; align-items: center; gap: 8px; padding: 0 4px 8px; border-bottom: 1px solid #e5e7eb; }
.path-bar :deep(.el-breadcrumb__inner) { font-family: ui-monospace, monospace; }
.entries { padding: 4px 0; }
.entry {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border-radius: 4px; cursor: pointer; font-size: 13px;
}
.entry:hover { background: #f3f4f6; }
.entry .name { flex: 1; }
.entry .size { color: #9ca3af; font-size: 11px; }
.empty { color: #9ca3af; text-align: center; padding: 20px; }
.file-preview {
  background: #1f2937; color: #f3f4f6; padding: 12px;
  border-radius: 6px; max-height: 60vh; overflow: auto;
  font-family: ui-monospace, monospace; font-size: 12px;
  white-space: pre-wrap; word-break: break-word;
}
</style>
