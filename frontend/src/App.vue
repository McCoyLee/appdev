<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Setting, Plus, ArrowDown } from '@element-plus/icons-vue'
import Workspace from './views/Workspace.vue'
import VaultDialog from './components/VaultDialog.vue'
import NewProjectDialog from './components/NewProjectDialog.vue'
import RepoSwitcher from './components/RepoSwitcher.vue'
import { health, repoApi } from './api/client'
import { useSessionStore } from './stores/session'
import { useVaultStore } from './stores/vault'

const sess = useSessionStore()
const vault = useVaultStore()
const ready = ref(false)
const status = ref({})
const vaultOpen = ref(false)
const newProjectOpen = ref(false)

async function onProjectCreated(repo) {
  vault.switchRepo(repo)  // 加入 recent 列表 + 设为当前
  sess.reset()
  ElMessage.success(`切换到 ${repo}`)
  await bootstrap()
}

async function onRepoSwitched(repo) {
  sess.reset()
  ElMessage.success(`切换到 ${repo}`)
  await bootstrap()
}

async function bootstrap() {
  ready.value = false
  try {
    const { data } = await health()
    status.value = data
    const hasAnyCreds = vault.configured || (data.deepseek_configured && data.github_configured)
    if (!hasAnyCreds) {
      vaultOpen.value = true
      return
    }
    const info = await repoApi.info()
    sess.user = info.data.user
    sess.repo = info.data.repo
    ready.value = true
  } catch (e) {
    const msg = e.response?.data?.detail || e.message
    if (e.response?.status === 401) {
      ElMessage.warning('凭据缺失或无效，请配置')
      vaultOpen.value = true
    } else {
      ElMessage.error('连接失败：' + msg)
    }
  }
}

onMounted(bootstrap)
</script>

<template>
  <el-container class="root">
    <el-header class="topbar">
      <div class="brand">
        <el-icon size="22"><Cpu /></el-icon>
        <span>AI 造应用</span>
      </div>
      <div class="repo-info" v-if="sess.repo">
        <el-tag type="success" effect="plain">
          <el-icon><User /></el-icon>
          {{ sess.user?.login }}
        </el-tag>
        <RepoSwitcher @switched="onRepoSwitched" />
        <el-tag v-if="sess.currentBranch" type="warning" effect="dark">
          <el-icon><Promotion /></el-icon> {{ sess.currentBranch }}
        </el-tag>
      </div>
      <div class="status">
        <el-button type="primary" size="small" @click="newProjectOpen = true">
          <el-icon><Plus /></el-icon>&nbsp;新建项目
        </el-button>
        <el-tag :type="vault.configured ? 'success' : 'warning'" size="small">
          {{ vault.configured ? '本地凭据 ✓' : '用 .env 凭据' }}
        </el-tag>
        <el-button :icon="Setting" link size="small" @click="vaultOpen = true" style="color: #f3f4f6">
          凭据
        </el-button>
      </div>
    </el-header>
    <el-main class="main">
      <Workspace v-if="ready" />
      <el-empty v-else description="连接后端中... 如果一直转，点右上角【凭据】按钮配置" />
    </el-main>
    <VaultDialog v-model="vaultOpen" @saved="bootstrap" />
    <NewProjectDialog v-model="newProjectOpen" @created="onProjectCreated" />
  </el-container>
</template>

<style>
html, body, #app { height: 100%; margin: 0; }
.root { height: 100vh; }
.topbar {
  display: flex; align-items: center; gap: 24px;
  background: #1f2937; color: #f3f4f6;
  height: 56px !important; padding: 0 20px;
}
.brand { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 16px; }
.repo-info { display: flex; align-items: center; gap: 8px; flex: 1; }
.status { display: flex; align-items: center; gap: 6px; }
.main { padding: 0; background: #f5f7fa; }
</style>
