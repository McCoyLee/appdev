<script setup>
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useVaultStore } from '../stores/vault'
import { useSessionStore } from '../stores/session'

const emit = defineEmits(['switched'])

const vault = useVaultStore()
const sess = useSessionStore()

const dropdownVisible = ref(false)
const newRepoInput = ref('')

const currentRepo = computed(() => vault.repo)
const recent = computed(() => vault.recentRepos.filter((r) => r !== currentRepo.value))

async function switchTo(repo) {
  if (repo === currentRepo.value) {
    dropdownVisible.value = false
    return
  }
  await vault.switchRepo(repo)
  emit('switched', repo)
  dropdownVisible.value = false
}

function addAndSwitch() {
  const r = newRepoInput.value.trim()
  if (!/^[^/]+\/[^/]+$/.test(r)) {
    return ElMessage.warning('格式应为 owner/name')
  }
  newRepoInput.value = ''
  switchTo(r)
}

async function removeRecent(repo) {
  try {
    await ElMessageBox.confirm(`从最近列表移除 ${repo}？仓库本身不会删。`, '确认', { type: 'warning' })
    await vault.removeRecent(repo)
  } catch {}
}
</script>

<template>
  <el-dropdown
    trigger="click"
    placement="bottom-start"
    :hide-on-click="false"
    @visible-change="(v) => (dropdownVisible = v)"
  >
    <el-tag type="primary" effect="dark" class="repo-tag" style="cursor: pointer">
      <span v-if="sess.repo">
        {{ sess.repo.full_name }} @ {{ sess.repo.default_branch }}
      </span>
      <span v-else>未选仓库</span>
      <el-icon style="margin-left: 4px"><ArrowDown /></el-icon>
    </el-tag>

    <template #dropdown>
      <div class="switcher-pop">
        <div class="section-title">最近使用</div>
        <el-empty v-if="!recent.length" :image-size="40" description="还没有其他仓库" />
        <div
          v-for="r in recent"
          :key="r"
          class="repo-row"
          @click="switchTo(r)"
        >
          <span class="repo-name">{{ r }}</span>
          <el-button
            link
            size="small"
            type="danger"
            @click.stop="removeRecent(r)"
          >移除</el-button>
        </div>

        <el-divider style="margin: 8px 0" />

        <div class="section-title">手动添加</div>
        <div class="add-row">
          <el-input
            v-model="newRepoInput"
            size="small"
            placeholder="owner/name"
            @keyup.enter="addAndSwitch"
          />
          <el-button size="small" type="primary" @click="addAndSwitch">切换</el-button>
        </div>
        <div class="hint">填一个你已经能访问的仓库，会切到那个会话</div>
      </div>
    </template>
  </el-dropdown>
</template>

<style scoped>
.repo-tag { font-family: ui-monospace, monospace; }
.switcher-pop { min-width: 340px; padding: 6px 8px; }
.section-title { color: #6b7280; font-size: 12px; padding: 4px 6px; }
.repo-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 8px; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.repo-row:hover { background: #f3f4f6; }
.repo-name { font-family: ui-monospace, monospace; }
.add-row { display: flex; gap: 6px; padding: 4px 6px; }
.hint { color: #9ca3af; font-size: 11px; padding: 2px 6px; }
</style>
