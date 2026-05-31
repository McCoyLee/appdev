<script setup>
import { ref } from 'vue'
import ChatPanel from '../components/ChatPanel.vue'
import PreviewPanel from '../components/PreviewPanel.vue'
import RepoTree from '../components/RepoTree.vue'
import SecretsPanel from '../components/SecretsPanel.vue'
import RunsPanel from '../components/RunsPanel.vue'
import TemplatesPanel from '../components/TemplatesPanel.vue'
import PrPanel from '../components/PrPanel.vue'

const sideTab = ref('preview')
</script>

<template>
  <div class="workspace">
    <div class="chat-col">
      <ChatPanel />
    </div>
    <div class="side-col">
      <el-tabs v-model="sideTab" class="side-tabs">
        <el-tab-pane label="预览" name="preview">
          <PreviewPanel />
        </el-tab-pane>
        <el-tab-pane label="仓库" name="tree">
          <RepoTree />
        </el-tab-pane>
        <el-tab-pane label="密码本" name="secrets">
          <SecretsPanel />
        </el-tab-pane>
        <el-tab-pane label="协作" name="prs">
          <PrPanel />
        </el-tab-pane>
        <el-tab-pane label="运行" name="runs">
          <RunsPanel />
        </el-tab-pane>
        <el-tab-pane label="模板" name="templates">
          <TemplatesPanel />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.workspace {
  display: grid;
  grid-template-columns: minmax(400px, 1fr) 540px;
  gap: 12px;
  height: calc(100vh - 56px);
  padding: 12px;
}
.chat-col, .side-col {
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.side-tabs { padding: 0 12px; height: 100%; display: flex; flex-direction: column; }
:deep(.side-tabs .el-tabs__content) { flex: 1; overflow: hidden; min-height: 0; }
:deep(.side-tabs .el-tab-pane) { height: 100%; overflow: auto; }
:deep(.side-tabs .el-tabs__nav-wrap)::after { height: 1px; }
</style>
