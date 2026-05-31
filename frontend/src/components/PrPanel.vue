<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { prsApi, branchesApi } from '../api/client'

const prs = ref([])
const state = ref('open')
const loading = ref(false)
const checksMap = ref({})  // { [prNumber]: 'success'|'failure'|'pending'|'none'|'loading' }

const CHECK_META = {
  success: { type: 'success', text: '✓ CI' },
  failure: { type: 'danger', text: '✗ CI' },
  pending: { type: 'warning', text: '… CI' },
  none: { type: 'info', text: '无 CI' },
  loading: { type: 'info', text: '…' },
}

async function loadChecks() {
  const map = {}
  prs.value.forEach((p) => { map[p.number] = 'loading' })
  checksMap.value = map
  await Promise.all(
    prs.value.map(async (p) => {
      try {
        const { data } = await prsApi.checks(p.number)
        checksMap.value = { ...checksMap.value, [p.number]: data.overall }
      } catch {
        checksMap.value = { ...checksMap.value, [p.number]: 'none' }
      }
    })
  )
}

// 新建 PR
const aiBranches = ref([])
const newPrHead = ref('')
const newPrTitle = ref('')
const creating = ref(false)

// 详情抽屉
const detailOpen = ref(false)
const detail = ref(null)
const detailLoading = ref(false)
const commentText = ref('')
const merging = ref(false)
const openFiles = ref(new Set())

function toggleFile(name) {
  const s = new Set(openFiles.value)
  s.has(name) ? s.delete(name) : s.add(name)
  openFiles.value = s
}

// 把 patch 解析成 [{text, cls, line}]，line 是「改动后新版本」的行号（可点击评论）
function parsePatch(patch) {
  let newLn = 0
  const out = []
  for (const ln of patch.split('\n')) {
    if (ln.startsWith('@@')) {
      const m = ln.match(/\+(\d+)/)
      newLn = m ? parseInt(m[1], 10) : newLn
      out.push({ text: ln, cls: 'hunk', line: null })
    } else if (ln.startsWith('+')) {
      out.push({ text: ln, cls: 'plus', line: newLn }); newLn++
    } else if (ln.startsWith('-')) {
      out.push({ text: ln, cls: 'minus', line: null })
    } else {
      out.push({ text: ln, cls: '', line: newLn }); newLn++
    }
  }
  return out
}

function reviewCommentsFor(file, line) {
  if (line == null || !detail.value?.review_comments) return []
  return detail.value.review_comments.filter((c) => c.path === file.filename && c.line === line)
}

// 当前正在写的行内评论草稿 { path, line, body }
const reviewDraft = ref(null)
function startReview(file, line) {
  if (line == null) return
  reviewDraft.value = { path: file.filename, line, body: '' }
}
async function submitReview() {
  const d = reviewDraft.value
  if (!d || !d.body.trim()) return
  try {
    const resp = await prsApi.reviewComment(detail.value.pr.number, d)
    detail.value.review_comments.push(resp.data.comment)
    reviewDraft.value = null
  } catch (e) {
    ElMessage.error('行内评论失败：' + (e.response?.data?.detail || e.message))
  }
}

async function load() {
  loading.value = true
  try {
    const [prResp, brResp] = await Promise.all([
      prsApi.list(state.value),
      branchesApi.list().catch(() => ({ data: { branches: [] } })),
    ])
    prs.value = prResp.data.prs || []
    aiBranches.value = (brResp.data.branches || []).map((b) => b.name)
    loadChecks()  // 不 await，徽章异步填充，不挡列表渲染
  } catch (e) {
    ElMessage.error('加载失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function prStateTag(p) {
  if (p.merged) return { type: 'success', text: '已合并' }
  if (p.state === 'closed') return { type: 'info', text: '已关闭' }
  if (p.draft) return { type: 'warning', text: '草稿' }
  return { type: 'primary', text: '开放中' }
}

async function createPr() {
  if (!newPrHead.value) {
    ElMessage.warning('先选一个要提的分支')
    return
  }
  creating.value = true
  try {
    const resp = await prsApi.create({
      head: newPrHead.value,
      base: 'main',
      title: newPrTitle.value || undefined,
    })
    ElMessage.success(resp.data.reused ? '已有 PR，帮你打开了' : '提好了 👍')
    newPrHead.value = ''
    newPrTitle.value = ''
    await load()
    openDetail(resp.data.pr.number)
  } catch (e) {
    ElMessage.error('提 PR 失败：' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

async function openDetail(number) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  openFiles.value = new Set()
  reviewDraft.value = null
  try {
    const resp = await prsApi.get(number)
    detail.value = resp.data
  } catch (e) {
    ElMessage.error('加载详情失败：' + (e.response?.data?.detail || e.message))
    detailOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

const checkType = computed(() => {
  const o = detail.value?.checks?.overall
  return { success: 'success', failure: 'danger', pending: 'warning', none: 'info' }[o] || 'info'
})
const checkText = computed(() => {
  const o = detail.value?.checks?.overall
  return { success: 'CI 通过', failure: 'CI 失败', pending: 'CI 进行中', none: '无 CI' }[o] || o
})

async function sendComment() {
  if (!commentText.value.trim()) return
  try {
    const resp = await prsApi.comment(detail.value.pr.number, commentText.value)
    detail.value.comments.push(resp.data.comment)
    commentText.value = ''
  } catch (e) {
    ElMessage.error('评论失败：' + (e.response?.data?.detail || e.message))
  }
}

async function mergePr() {
  const num = detail.value.pr.number
  try {
    await ElMessageBox.confirm(
      `确定合并 PR #${num}「${detail.value.pr.title}」到 ${detail.value.pr.base}？合并后会删掉这个 AI 分支并刷新预览。`,
      '合并确认',
      { confirmButtonText: '合并', cancelButtonText: '再想想', type: 'warning' }
    )
  } catch {
    return
  }
  merging.value = true
  try {
    const resp = await prsApi.merge(num, 'squash')
    ElMessage.success(`已合并 → ${resp.data.base}` + (resp.data.branch_deleted ? '，分支已清理' : ''))
    detailOpen.value = false
    await load()
  } catch (e) {
    ElMessage.error('合并失败：' + (e.response?.data?.detail || e.message))
  } finally {
    merging.value = false
  }
}

async function closePr() {
  const num = detail.value.pr.number
  try {
    await ElMessageBox.confirm(`关闭 PR #${num}（不合并）？`, '提示', {
      confirmButtonText: '关闭它', cancelButtonText: '取消', type: 'warning',
    })
  } catch {
    return
  }
  try {
    await prsApi.close(num)
    ElMessage.success('已关闭')
    detailOpen.value = false
    await load()
  } catch (e) {
    ElMessage.error('关闭失败：' + (e.response?.data?.detail || e.message))
  }
}

onMounted(load)
</script>

<template>
  <div class="pr-panel">
    <div class="bar">
      <el-radio-group v-model="state" size="small" @change="load">
        <el-radio-button label="open">开放中</el-radio-button>
        <el-radio-button label="closed">已关闭</el-radio-button>
        <el-radio-button label="all">全部</el-radio-button>
      </el-radio-group>
      <el-button :icon="Refresh" size="small" @click="load" style="margin-left: auto">刷新</el-button>
    </div>

    <div class="new-pr">
      <el-select v-model="newPrHead" placeholder="选一个 AI 分支提 PR" size="small" filterable
                 no-data-text="暂无 ai/* 分支" style="width: 200px">
        <el-option v-for="b in aiBranches" :key="b" :label="b" :value="b" />
      </el-select>
      <el-input v-model="newPrTitle" size="small" placeholder="标题（可选）" style="flex: 1" />
      <el-button type="primary" size="small" :icon="Plus" :loading="creating" @click="createPr">提 PR</el-button>
    </div>

    <el-table v-loading="loading" :data="prs" size="small" empty-text="还没有 PR" @row-click="(r) => openDetail(r.number)"
              style="cursor: pointer">
      <el-table-column label="#" prop="number" width="50" />
      <el-table-column label="标题" prop="title" show-overflow-tooltip />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="prStateTag(row).type" size="small">{{ prStateTag(row).text }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="CI" width="62">
        <template #default="{ row }">
          <el-tag
            v-if="checksMap[row.number]"
            :type="(CHECK_META[checksMap[row.number]] || CHECK_META.none).type"
            size="small"
            effect="plain"
          >{{ (CHECK_META[checksMap[row.number]] || CHECK_META.none).text }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="分支" prop="head" width="110" show-overflow-tooltip />
    </el-table>

    <el-drawer v-model="detailOpen" :title="detail ? `PR #${detail.pr.number}` : '加载中'" size="60%" direction="rtl">
      <div v-loading="detailLoading" class="detail">
        <template v-if="detail">
          <h3>{{ detail.pr.title }}</h3>
          <div class="meta">
            <el-tag :type="prStateTag(detail.pr).type" size="small">{{ prStateTag(detail.pr).text }}</el-tag>
            <el-tag :type="checkType" size="small">{{ checkText }}</el-tag>
            <span class="dim">{{ detail.pr.head }} → {{ detail.pr.base }}</span>
            <span class="dim">by {{ detail.pr.user }}</span>
            <el-link :href="detail.pr.html_url" target="_blank" type="info" style="margin-left:auto">在 GitHub 打开 ↗</el-link>
          </div>

          <p v-if="detail.body" class="body">{{ detail.body }}</p>

          <h4>改动文件（{{ detail.files.length }}）</h4>
          <ul class="files">
            <li v-for="f in detail.files" :key="f.filename">
              <div class="frow" :class="{ clickable: f.patch }" @click="toggleFile(f.filename)">
                <span class="caret" v-if="f.patch">{{ openFiles.has(f.filename) ? '▾' : '▸' }}</span>
                <span class="caret" v-else>&nbsp;</span>
                <span :class="['fstat', f.status]">{{ f.status[0].toUpperCase() }}</span>
                <span class="fname">{{ f.filename }}</span>
                <span class="add">+{{ f.additions }}</span> <span class="del">-{{ f.deletions }}</span>
              </div>
              <div v-if="f.patch && openFiles.has(f.filename)" class="diff-wrap">
                <pre class="diff"><code><template v-for="(row, i) in parsePatch(f.patch)" :key="i"><span class="dline" :class="[row.cls, { commentable: row.line != null }]" @click="startReview(f, row.line)"><span class="lno">{{ row.line ?? '' }}</span>{{ row.text || ' ' }}</span><span v-for="(rc, j) in reviewCommentsFor(f, row.line)" :key="'rc' + i + '-' + j" class="inline-rc">💬 <b>{{ rc.user }}</b>：{{ rc.body }}</span></template></code></pre>
                <div v-if="reviewDraft && reviewDraft.path === f.filename" class="rc-box">
                  <span class="dim">就「{{ f.filename }}」第 {{ reviewDraft.line }} 行：</span>
                  <el-input v-model="reviewDraft.body" type="textarea" :rows="2" size="small" placeholder="行内评论…" />
                  <div class="rc-actions">
                    <el-button size="small" type="primary" @click="submitReview">发表</el-button>
                    <el-button size="small" @click="reviewDraft = null">取消</el-button>
                  </div>
                </div>
              </div>
            </li>
          </ul>

          <h4>CI 检查</h4>
          <ul class="checks">
            <li v-for="(c, i) in detail.checks.checks" :key="i">
              <el-tag size="small" :type="c.conclusion === 'success' ? 'success' : c.conclusion === 'failure' ? 'danger' : 'warning'">
                {{ c.status === 'completed' ? (c.conclusion || '?') : c.status }}
              </el-tag>
              {{ c.name }}
            </li>
            <li v-if="!detail.checks.checks.length" class="dim">还没有 CI 检查</li>
          </ul>

          <h4>讨论（{{ detail.comments.length }}）</h4>
          <div class="comments">
            <div v-for="(c, i) in detail.comments" :key="i" class="comment">
              <b>{{ c.user }}</b>
              <span class="dim">{{ new Date(c.created_at).toLocaleString() }}</span>
              <div>{{ c.body }}</div>
            </div>
            <p v-if="!detail.comments.length" class="dim">还没人留言</p>
          </div>
          <div class="comment-box">
            <el-input v-model="commentText" type="textarea" :rows="2" placeholder="说点什么…" size="small" />
            <el-button size="small" @click="sendComment">发表</el-button>
          </div>

          <div class="actions" v-if="detail.pr.state === 'open' && !detail.pr.merged">
            <el-button type="success" :loading="merging" @click="mergePr">合并这版 ✅</el-button>
            <el-button @click="closePr">关闭不合并</el-button>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.pr-panel { padding: 8px 4px; }
.bar { display: flex; align-items: center; margin-bottom: 8px; }
.new-pr { display: flex; gap: 6px; align-items: center; margin-bottom: 10px; }
.detail h3 { margin: 0 0 8px; }
.meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.dim { color: #9ca3af; font-size: 12px; }
.body { white-space: pre-wrap; background: #f9fafb; padding: 8px; border-radius: 6px; font-size: 13px; }
h4 { margin: 14px 0 6px; font-size: 13px; color: #6b7280; font-weight: 500; }
.files, .checks { list-style: none; padding: 0; margin: 0; font-size: 13px; }
.files li, .checks li { padding: 3px 0; }
.frow { display: flex; align-items: center; gap: 4px; }
.frow.clickable { cursor: pointer; }
.frow.clickable:hover { background: #f9fafb; }
.caret { width: 12px; color: #9ca3af; font-size: 11px; }
.fname { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.diff {
  margin: 4px 0 8px 16px; padding: 6px 8px; background: #0d1117; border-radius: 6px;
  overflow-x: auto; font-size: 12px; line-height: 1.5;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
.diff code { display: block; }
.diff .dline { display: block; white-space: pre; color: #c9d1d9; }
.diff .dline.commentable { cursor: pointer; }
.diff .dline.commentable:hover { background: rgba(88,166,255,.18); }
.diff .lno { display: inline-block; width: 34px; margin-right: 8px; color: #6e7681; text-align: right; user-select: none; }
.diff .hunk { color: #8b949e; background: #161b22; }
.diff .plus { color: #3fb950; background: rgba(63,185,80,.12); }
.diff .minus { color: #f85149; background: rgba(248,81,73,.12); }
.diff .inline-rc { display: block; white-space: pre-wrap; color: #adbac7; background: #1c2333; border-left: 2px solid #58a6ff; padding: 4px 8px 4px 42px; margin: 2px 0; }
.diff .inline-rc b { color: #58a6ff; }
.rc-box { margin: 6px 0 10px 16px; }
.rc-actions { margin-top: 4px; display: flex; gap: 6px; }
.fstat { display: inline-block; width: 16px; text-align: center; border-radius: 3px; font-size: 11px; margin-right: 4px; color: white; flex-shrink: 0; }
.fstat.added { background: #16a34a; }
.fstat.modified { background: #ca8a04; }
.fstat.removed { background: #dc2626; }
.fstat.renamed { background: #6b7280; }
.add { color: #16a34a; } .del { color: #dc2626; }
.comments { max-height: 200px; overflow: auto; }
.comment { padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.comment b { margin-right: 6px; }
.comment-box { display: flex; gap: 6px; align-items: flex-end; margin-top: 8px; }
.actions { margin-top: 16px; display: flex; gap: 8px; }
</style>
