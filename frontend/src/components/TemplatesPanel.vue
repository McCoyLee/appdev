<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { templatesApi } from '../api/client'

const templates = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await templatesApi.list()
    templates.value = data.templates || []
  } catch (e) {
    ElMessage.error('加载失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="tpl-panel">
    <el-alert type="info" :closable="false" show-icon class="hint">
      架构当前支持以下项目形态。新建项目时可选；现有仓库可以让 AI 在此基础上改写。
    </el-alert>

    <el-empty v-if="!templates.length && !loading" description="还没有模板" />

    <div v-for="t in templates" :key="t.id" class="tpl-card">
      <div class="tpl-head">
        <h4>{{ t.name }}</h4>
        <div class="tags">
          <el-tag v-for="tag in t.tags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
        </div>
      </div>
      <p class="desc">{{ t.description }}</p>
      <div class="meta">
        <div><b>部署目标：</b>{{ t.deploy_target }}</div>
        <div v-if="t.required_secrets?.length">
          <b>需要的密钥：</b>
          <div class="secrets">
            <el-tag
              v-for="s in t.required_secrets"
              :key="s.name"
              type="warning"
              size="small"
              effect="plain"
            >
              🔒 {{ s.name }}
            </el-tag>
          </div>
          <ul class="secret-desc">
            <li v-for="s in t.required_secrets" :key="s.name">
              <b>{{ s.name }}</b> — {{ s.description }}
            </li>
          </ul>
        </div>
        <div v-if="t.primary_files?.length">
          <b>主要文件：</b>
          <code v-for="f in t.primary_files" :key="f" class="file-tag">{{ f }}</code>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tpl-panel { padding: 8px 4px; }
.hint { margin-bottom: 12px; }
.tpl-card {
  border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 12px 14px; margin-bottom: 10px; background: white;
}
.tpl-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.tpl-head h4 { margin: 0; font-size: 14px; }
.tags { display: flex; gap: 4px; }
.desc { color: #4b5563; font-size: 12px; margin: 6px 0; line-height: 1.6; }
.meta { font-size: 12px; color: #374151; }
.meta > div { margin-top: 4px; }
.secrets { display: inline-flex; gap: 4px; margin-left: 4px; }
.secret-desc { margin: 4px 0 0 16px; padding: 0; font-size: 11px; color: #6b7280; }
.secret-desc li { margin-bottom: 2px; }
.file-tag {
  display: inline-block; padding: 1px 6px; margin: 2px 2px 0 0;
  background: #f3f4f6; color: #2563eb; border-radius: 4px; font-size: 11px;
}
</style>
