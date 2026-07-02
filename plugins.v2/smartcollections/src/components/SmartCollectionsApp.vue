<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { unwrapResponse } from '../provider'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'SmartCollections' },
  hideTitle: { type: Boolean, default: false },
})

const loading = ref(false)
const actionLoading = ref('')
const error = ref('')
const notice = ref('')
const tab = ref('sources')
const sourceTab = ref('tmdb')
const status = ref({ catalog: { tmdb: [], douban: [] }, templates: [], collections: [], history: [] })
const selectedSources = ref([])
const manualUrl = ref('')
const preview = ref(null)
const collectionName = ref('')
const selectedPreviewKeys = ref([])
const templateDialog = ref(false)
const templateName = ref('')
const templateDescription = ref('')
const importDialog = ref(false)
const importText = ref('')
const previewAnchor = ref(null)
const enlargedPoster = ref('')
const enlargedPosterTitle = ref('')
const subscribingKeys = ref([])
const subscribedKeys = ref([])
const posterDialog = ref(false)
const posterCollection = ref(null)
const posterFile = ref(null)

const pluginBase = computed(() => `plugin/${props.pluginId || 'SmartCollections'}`)
const sourceItems = computed(() => status.value.catalog?.[sourceTab.value] || [])
const matchedItems = computed(() => (preview.value?.items || []).filter(item => item.matched))
const visiblePreviewItems = computed(() => (preview.value?.items || []).slice(0, 300))
const allCurrentSelected = computed(() => {
  const keys = sourceItems.value.map(item => item.id)
  return keys.length > 0 && keys.every(key => selectedSources.value.includes(key))
})

function clearMessages() {
  error.value = ''
  notice.value = ''
}

function assertResponse(response) {
  if (response?.success === false) throw new Error(response.message || '操作失败')
  return unwrapResponse(response)
}

async function loadStatus() {
  loading.value = true
  clearMessages()
  try {
    status.value = assertResponse(await props.api.get(`${pluginBase.value}/status`)) || status.value
  } catch (err) {
    error.value = err?.message || '页面数据加载失败'
  } finally {
    loading.value = false
  }
}

function selectAllCurrent() {
  const current = sourceItems.value.map(item => item.id)
  if (allCurrentSelected.value) {
    selectedSources.value = selectedSources.value.filter(key => !current.includes(key))
  } else {
    selectedSources.value = [...new Set([...selectedSources.value, ...current])]
  }
}

async function runPreview(source) {
  actionLoading.value = `preview:${source.id || source.template_id || source.url}`
  clearMessages()
  try {
    const data = assertResponse(await props.api.post(`${pluginBase.value}/preview`, source))
    preview.value = data
    collectionName.value = data.title || source.name || ''
    selectedPreviewKeys.value = (data.items || []).filter(item => item.matched).map(item => item.key)
    await nextTick()
    previewAnchor.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  } catch (err) {
    error.value = err?.message || '预览失败'
  } finally {
    actionLoading.value = ''
  }
}

async function previewManual() {
  if (!manualUrl.value.trim()) {
    error.value = '请输入公开 TMDB List 或豆瓣豆列链接'
    return
  }
  await runPreview({ id: 'manual', source_type: 'manual', url: manualUrl.value.trim() })
}

async function syncPreview() {
  if (!preview.value?.preview_id) return
  actionLoading.value = 'sync-preview'
  clearMessages()
  try {
    const result = assertResponse(await props.api.post(`${pluginBase.value}/preview/sync`, {
      preview_id: preview.value.preview_id,
      name: collectionName.value.trim(),
      selected_keys: selectedPreviewKeys.value,
    }))
    await loadStatus()
    notice.value = `已同步「${result.name}」：匹配 ${result.matched}，新增 ${result.added}，移除 ${result.removed}`
  } catch (err) {
    error.value = err?.message || '同步失败'
  } finally {
    actionLoading.value = ''
  }
}

async function batchSync() {
  const all = [...(status.value.catalog?.tmdb || []), ...(status.value.catalog?.douban || [])]
  const sources = all.filter(item => selectedSources.value.includes(item.id))
  if (!sources.length) {
    error.value = '请先选择片单'
    return
  }
  if (!window.confirm(`将依次预览并同步 ${sources.length} 个 Emby 合集，继续吗？`)) return
  actionLoading.value = 'batch-sync'
  clearMessages()
  try {
    const response = await props.api.post(`${pluginBase.value}/batch/sync`, { sources })
    const results = unwrapResponse(response) || []
    if (response?.success === false && !results.length) throw new Error(response.message || '批量同步失败')
    const ok = results.filter(item => item.success).length
    await loadStatus()
    notice.value = `批量同步完成：成功 ${ok} / ${results.length}`
  } catch (err) {
    error.value = err?.message || '批量同步失败'
  } finally {
    actionLoading.value = ''
  }
}

function openTemplateDialog() {
  if (!preview.value) return
  templateName.value = collectionName.value || preview.value.title || ''
  templateDescription.value = preview.value.description || ''
  templateDialog.value = true
}

async function saveTemplate() {
  actionLoading.value = 'save-template'
  clearMessages()
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/templates/save`, {
      preview_id: preview.value.preview_id,
      name: templateName.value,
      description: templateDescription.value,
    }))
    templateDialog.value = false
    await loadStatus()
    notice.value = '模板已保存'
  } catch (err) {
    error.value = err?.message || '保存模板失败'
  } finally {
    actionLoading.value = ''
  }
}

async function deleteTemplate(template) {
  if (!window.confirm(`删除模板「${template.name}」？`)) return
  clearMessages()
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/templates/delete`, { template_id: template.id }))
    await loadStatus()
    notice.value = '模板已删除'
  } catch (err) {
    error.value = err?.message || '删除模板失败'
  }
}

async function exportTemplates() {
  const payload = JSON.stringify({ version: 1, templates: status.value.templates || [] }, null, 2)
  await navigator.clipboard.writeText(payload)
  notice.value = '模板 JSON 已复制到剪贴板'
}

async function importTemplates() {
  clearMessages()
  try {
    const parsed = JSON.parse(importText.value)
    const templates = Array.isArray(parsed) ? parsed : parsed.templates
    const result = assertResponse(await props.api.post(`${pluginBase.value}/templates/import`, { templates }))
    importDialog.value = false
    importText.value = ''
    await loadStatus()
    notice.value = `已导入 ${result.imported} 个模板`
  } catch (err) {
    error.value = err?.message || '模板 JSON 无效'
  }
}

async function resyncCollection(collection) {
  actionLoading.value = `resync:${collection.id}`
  clearMessages()
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/collections/resync`, { collection_id: collection.id }))
    await loadStatus()
    notice.value = `「${collection.name}」已重新同步`
  } catch (err) {
    error.value = err?.message || '重新同步失败'
  } finally {
    actionLoading.value = ''
  }
}

async function deleteCollection(collection) {
  if (!window.confirm(`删除「${collection.name}」的管理记录及 Emby 合集？此操作不可撤销。`)) return
  clearMessages()
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/collections/delete`, {
      collection_id: collection.id,
      delete_emby: true,
    }))
    await loadStatus()
    notice.value = '合集已删除'
  } catch (err) {
    error.value = err?.message || '删除合集失败'
  }
}

async function subscribeItem(item) {
  if (!item.tmdb_id || !item.media_type || subscribingKeys.value.includes(item.key)) return
  subscribingKeys.value = [...subscribingKeys.value, item.key]
  clearMessages()
  try {
    const response = await props.api.post(`${pluginBase.value}/subscribe`, {
      tmdb_id: item.tmdb_id,
      media_type: item.media_type,
      title: item.title,
      year: item.year,
    })
    const result = assertResponse(response) || {}
    subscribedKeys.value = [...new Set([...subscribedKeys.value, item.key])]
    notice.value = result.already_exists
      ? `「${item.title}」已经订阅，已立即搜索资源`
      : `已订阅「${item.title}」并立即搜索资源`
  } catch (err) {
    error.value = err?.message || '添加订阅失败'
  } finally {
    subscribingKeys.value = subscribingKeys.value.filter(key => key !== item.key)
  }
}

function showPoster(item) {
  if (!item?.poster_url) return
  enlargedPoster.value = item.poster_url
  enlargedPosterTitle.value = item.title || '海报'
}

function openPosterManager(collection) {
  posterCollection.value = collection
  posterFile.value = null
  posterDialog.value = true
}

async function generateCollectionPoster() {
  if (!posterCollection.value) return
  actionLoading.value = `poster-auto:${posterCollection.value.id}`
  clearMessages()
  try {
    const response = await props.api.post(`${pluginBase.value}/collections/poster/auto`, {
      collection_id: posterCollection.value.id,
    })
    assertResponse(response)
    const name = posterCollection.value.name
    posterDialog.value = false
    await loadStatus()
    notice.value = `「${name}」合集海报已重新生成`
  } catch (err) {
    error.value = err?.message || '自动生成海报失败'
  } finally {
    actionLoading.value = ''
  }
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('读取图片失败'))
    reader.readAsDataURL(file)
  })
}

async function uploadCollectionPoster() {
  const file = Array.isArray(posterFile.value) ? posterFile.value[0] : posterFile.value
  if (!posterCollection.value || !file) {
    error.value = '请先选择一张海报图片'
    return
  }
  actionLoading.value = `poster-upload:${posterCollection.value.id}`
  clearMessages()
  try {
    const image = await readFileAsDataUrl(file)
    const response = await props.api.post(`${pluginBase.value}/collections/poster/upload`, {
      collection_id: posterCollection.value.id,
      image,
    })
    assertResponse(response)
    const name = posterCollection.value.name
    posterDialog.value = false
    await loadStatus()
    notice.value = `「${name}」自定义海报已上传`
  } catch (err) {
    error.value = err?.message || '上传海报失败'
  } finally {
    actionLoading.value = ''
  }
}

function tmdbLink(item) {
  if (!item.tmdb_id) return ''
  return `https://www.themoviedb.org/${item.media_type === 'tv' ? 'tv' : 'movie'}/${item.tmdb_id}`
}

defineExpose({ loadStatus, loading })
onMounted(loadStatus)
</script>

<template>
  <div class="smart-page pa-4 pa-md-6">
    <div v-if="!hideTitle" class="page-header d-flex flex-wrap align-center ga-3 mb-5">
      <div>
        <div class="text-h4 font-weight-bold">🎬 智能合集</div>
        <div class="text-body-1 text-medium-emphasis mt-1">从公开片单、豆瓣豆列或模板创建 Emby 合集，先预览，再同步。</div>
      </div>
      <VSpacer />
      <VChip class="server-chip" prepend-icon="mdi-server" variant="tonal">{{ status.server || '未选择 Emby' }}</VChip>
      <VBtn icon="mdi-refresh" variant="text" :loading="loading" @click="loadStatus" />
    </div>

    <VAlert v-if="error" type="error" variant="tonal" closable class="mb-4" @click:close="error = ''">{{ error }}</VAlert>
    <VAlert v-if="notice" type="success" variant="tonal" closable class="mb-4" @click:close="notice = ''">{{ notice }}</VAlert>
    <VProgressLinear v-if="loading || actionLoading" indeterminate color="primary" class="mb-4" />

    <VCard rounded="xl" variant="outlined" class="mb-5">
      <VTabs v-model="tab" color="primary" grow>
        <VTab value="sources" prepend-icon="mdi-format-list-checks">片单与模板</VTab>
        <VTab value="templates" prepend-icon="mdi-bookmark-box-multiple">我的模板</VTab>
        <VTab value="collections" prepend-icon="mdi-folder-star-multiple">已同步合集</VTab>
      </VTabs>
    </VCard>

    <VWindow v-model="tab">
      <VWindowItem value="sources">
        <VCard rounded="xl" variant="outlined" class="mb-5">
          <VCardTitle class="d-flex flex-wrap align-center ga-2 pa-5">
            <div>
              <div class="text-h6">片单目录</div>
              <div class="text-body-2 text-medium-emphasis">选择一个预览，或多选后批量同步。</div>
            </div>
            <VSpacer />
            <VBtn variant="text" prepend-icon="mdi-select-all" @click="selectAllCurrent">{{ allCurrentSelected ? '取消本页全选' : '本页全选' }}</VBtn>
            <VBtn color="primary" prepend-icon="mdi-sync" :loading="actionLoading === 'batch-sync'" @click="batchSync">批量同步（{{ selectedSources.length }}）</VBtn>
          </VCardTitle>
          <VDivider />
          <VCardText class="pa-5">
            <VTabs v-model="sourceTab" density="comfortable" color="primary" class="mb-4">
              <VTab value="tmdb">TMDB 公开片单</VTab>
              <VTab value="douban">热门豆列</VTab>
            </VTabs>
            <VRow>
              <VCol v-for="source in sourceItems" :key="source.id" cols="12" sm="6" lg="4">
                <VCard rounded="lg" variant="outlined" class="source-card h-100">
                  <VCardText class="d-flex ga-3">
                    <VCheckboxBtn v-model="selectedSources" :value="source.id" color="primary" />
                    <VAvatar :color="sourceTab === 'douban' ? 'green' : 'blue'" variant="tonal" rounded="lg">
                      <VIcon :icon="sourceTab === 'douban' ? 'mdi-alpha-d-box' : 'mdi-movie-open-star'" />
                    </VAvatar>
                    <div class="flex-grow-1 min-width-0">
                      <div class="font-weight-medium text-truncate">{{ source.name }}</div>
                      <div class="text-caption text-medium-emphasis mt-1">{{ sourceTab === 'douban' ? `豆列 ${source.list_id}` : source.media_type === 'tv' ? '剧集片单' : '电影片单' }}</div>
                    </div>
                  </VCardText>
                  <VCardActions class="px-4 pb-4">
                    <VBtn
                      v-if="source.url"
                      :href="source.url"
                      target="_blank"
                      rel="noopener"
                      size="small"
                      variant="text"
                      prepend-icon="mdi-open-in-new"
                    >来源</VBtn>
                    <VSpacer />
                    <VBtn size="small" variant="tonal" prepend-icon="mdi-eye" :loading="actionLoading === `preview:${source.id}`" @click="runPreview(source)">预览匹配</VBtn>
                  </VCardActions>
                </VCard>
              </VCol>
            </VRow>
          </VCardText>
        </VCard>

        <VCard rounded="xl" variant="outlined" class="mb-5">
          <VCardText class="pa-5">
            <div class="text-h6 mb-1">手动输入公开片单</div>
            <div class="text-body-2 text-medium-emphasis mb-4">支持 TMDB List 和豆瓣豆列链接。</div>
            <div class="d-flex flex-column flex-md-row ga-3">
              <VTextField v-model="manualUrl" label="片单链接" placeholder="https://www.themoviedb.org/list/... 或 https://www.douban.com/doulist/.../" hide-details />
              <VBtn color="primary" size="large" prepend-icon="mdi-eye" :loading="actionLoading === 'preview:manual'" @click="previewManual">预览匹配</VBtn>
            </div>
          </VCardText>
        </VCard>
      </VWindowItem>

      <VWindowItem value="templates">
        <div class="d-flex flex-wrap align-center ga-2 mb-4">
          <div><div class="text-h6">我的模板</div><div class="text-body-2 text-medium-emphasis">模板保存的是已解析的 TMDB 条目，可导入导出。</div></div>
          <VSpacer />
          <VBtn variant="tonal" prepend-icon="mdi-export" :disabled="!status.templates?.length" @click="exportTemplates">导出全部</VBtn>
          <VBtn variant="tonal" prepend-icon="mdi-import" @click="importDialog = true">导入模板</VBtn>
        </div>
        <VRow v-if="status.templates?.length">
          <VCol v-for="template in status.templates" :key="template.id" cols="12" md="6" lg="4">
            <VCard rounded="xl" variant="outlined" class="h-100">
              <VCardText>
                <VAvatar color="purple" variant="tonal" rounded="lg" class="mb-3"><VIcon icon="mdi-bookmark-star" /></VAvatar>
                <div class="text-h6">{{ template.name }}</div>
                <div class="text-body-2 text-medium-emphasis mt-1">{{ template.description || '自定义智能合集模板' }}</div>
                <VChip size="small" class="mt-3">{{ template.item_count || template.items?.length || 0 }} 个条目</VChip>
              </VCardText>
              <VCardActions>
                <VBtn color="primary" variant="tonal" prepend-icon="mdi-eye" @click="runPreview({ template_id: template.id, id: template.id })">预览</VBtn>
                <VSpacer />
                <VBtn icon="mdi-delete-outline" color="error" variant="text" @click="deleteTemplate(template)" />
              </VCardActions>
            </VCard>
          </VCol>
        </VRow>
        <VAlert v-else type="info" variant="tonal">预览任意片单后，可将结果保存为模板。</VAlert>
      </VWindowItem>

      <VWindowItem value="collections">
        <div class="text-h6 mb-1">已同步合集</div>
        <div class="text-body-2 text-medium-emphasis mb-4">重新同步来源，或同时删除管理记录和 Emby 合集。</div>
        <VRow v-if="status.collections?.length">
          <VCol v-for="collection in status.collections" :key="collection.id" cols="12" md="6">
            <VCard rounded="xl" variant="outlined">
              <VCardText>
                <div class="d-flex align-start ga-3">
                  <VAvatar color="green" variant="tonal" rounded="lg"><VIcon icon="mdi-folder-star" /></VAvatar>
                  <div class="flex-grow-1">
                    <div class="text-h6">{{ collection.name }}</div>
                    <div class="text-body-2 text-medium-emphasis">{{ collection.source }} · 最近同步 {{ collection.last_sync_at }}</div>
                    <a v-if="collection.source_url" :href="collection.source_url" target="_blank" rel="noopener" class="source-link text-caption">
                      <VIcon icon="mdi-link-variant" size="small" class="me-1" />查看片单来源
                    </a>
                  </div>
                  <VChip color="success" variant="tonal">{{ collection.matched_count }}/{{ collection.total_count }}</VChip>
                </div>
                <VChip v-if="collection.poster_source" size="small" variant="tonal" color="purple" class="mt-3">
                  {{ collection.poster_source === 'custom' ? '自定义海报' : '自动海报' }}
                </VChip>
              </VCardText>
              <VCardActions class="flex-wrap">
                <VBtn variant="tonal" prepend-icon="mdi-sync" :loading="actionLoading === `resync:${collection.id}`" @click="resyncCollection(collection)">重新同步</VBtn>
                <VBtn variant="tonal" prepend-icon="mdi-image-edit" @click="openPosterManager(collection)">海报</VBtn>
                <VSpacer />
                <VBtn color="error" variant="text" prepend-icon="mdi-delete-outline" @click="deleteCollection(collection)">删除</VBtn>
              </VCardActions>
            </VCard>
          </VCol>
        </VRow>
        <VAlert v-else type="info" variant="tonal">还没有由本插件同步并管理的 Emby 合集。</VAlert>
      </VWindowItem>
    </VWindow>

    <div v-if="preview" ref="previewAnchor" class="preview-anchor pt-2">
      <VCard rounded="xl" variant="outlined" class="mt-4">
        <VCardTitle class="d-flex flex-wrap align-center ga-3 pa-5">
          <div class="flex-grow-1">
            <div class="text-h6">{{ preview.title }}</div>
            <div class="text-body-2 text-medium-emphasis">共 {{ preview.total_count }} · 电影 {{ preview.movie_count }} · 剧集 {{ preview.tv_count }} · Emby 已有 {{ preview.matched_count }} · 缺失 {{ preview.missing_count }}</div>
            <a v-if="preview.source_url" :href="preview.source_url" target="_blank" rel="noopener" class="source-link text-caption">
              <VIcon icon="mdi-open-in-new" size="small" class="me-1" />{{ preview.source_url }}
            </a>
          </div>
          <VTextField v-model="collectionName" label="合集名称" density="compact" hide-details class="collection-name" />
          <VBtn color="success" prepend-icon="mdi-folder-plus" :disabled="!selectedPreviewKeys.length" :loading="actionLoading === 'sync-preview'" @click="syncPreview">同步至 Emby（{{ selectedPreviewKeys.length }}）</VBtn>
          <VBtn color="primary" variant="tonal" prepend-icon="mdi-bookmark-plus" @click="openTemplateDialog">保存为模板</VBtn>
        </VCardTitle>
        <VDivider />
        <VCardText class="pa-4">
          <VRow class="mb-3">
            <VCol cols="6" md="3"><VCard color="blue" variant="tonal"><VCardText><div class="text-caption">列表总数</div><div class="text-h5">{{ preview.total_count }}</div></VCardText></VCard></VCol>
            <VCol cols="6" md="3"><VCard color="cyan" variant="tonal"><VCardText><div class="text-caption">电影 / 剧集</div><div class="text-h5">{{ preview.movie_count }} / {{ preview.tv_count }}</div></VCardText></VCard></VCol>
            <VCol cols="6" md="3"><VCard color="success" variant="tonal"><VCardText><div class="text-caption">已匹配</div><div class="text-h5">{{ preview.matched_count }}</div></VCardText></VCard></VCol>
            <VCol cols="6" md="3"><VCard color="warning" variant="tonal"><VCardText><div class="text-caption">缺失</div><div class="text-h5">{{ preview.missing_count }}</div></VCardText></VCard></VCol>
          </VRow>
          <div class="preview-table">
            <VTable hover density="comfortable">
              <thead><tr><th></th><th>#</th><th>海报</th><th>状态</th><th>标题</th><th>Emby 匹配</th></tr></thead>
              <tbody>
                <tr v-for="item in visiblePreviewItems" :key="item.key">
                  <td><VCheckboxBtn v-if="item.matched" v-model="selectedPreviewKeys" :value="item.key" color="success" /></td>
                  <td>{{ item.position }}</td>
                  <td>
                    <VImg
                      :src="item.poster_url"
                      width="42"
                      height="62"
                      cover
                      :class="['poster', 'rounded', { 'poster-clickable': item.poster_url }]"
                      @click="showPoster(item)"
                    />
                  </td>
                  <td><VChip :color="item.matched ? 'success' : 'default'" size="small" variant="tonal">{{ item.matched ? '已匹配' : '缺失' }}</VChip></td>
                  <td>
                    <a v-if="tmdbLink(item)" :href="tmdbLink(item)" target="_blank" class="item-link">{{ item.title }}</a><span v-else>{{ item.title }}</span>
                    <span class="text-medium-emphasis"> {{ item.year ? `(${item.year})` : '' }}</span>
                    <VChip size="x-small" class="ms-2">{{ item.media_type === 'tv' ? '剧集' : '电影' }}</VChip>
                    <VBtn
                      v-if="!item.matched && item.tmdb_id"
                      size="x-small"
                      color="primary"
                      variant="tonal"
                      class="ms-2"
                      prepend-icon="mdi-bell-plus-outline"
                      :loading="subscribingKeys.includes(item.key)"
                      :disabled="subscribedKeys.includes(item.key)"
                      @click="subscribeItem(item)"
                    >{{ subscribedKeys.includes(item.key) ? '已订阅' : '订阅' }}</VBtn>
                    <div v-if="!item.matched" class="text-caption text-medium-emphasis">{{ item.missing_reason }}</div>
                  </td>
                  <td>
                    <a v-if="item.emby_url" :href="item.emby_url" target="_blank" rel="noopener" class="emby-link">{{ item.emby_name }}</a>
                    <span v-else class="text-medium-emphasis">{{ item.emby_name || '—' }}</span>
                    <span v-if="item.match_method === 'title'" class="text-caption text-medium-emphasis">（标题兜底）</span>
                  </td>
                </tr>
              </tbody>
            </VTable>
          </div>
          <VAlert v-if="preview.items?.length > 300" type="info" variant="tonal" class="mt-3">页面只展示前 300 条；同步仍会处理全部条目。</VAlert>
        </VCardText>
      </VCard>
    </div>

    <VDialog v-model="templateDialog" max-width="560">
      <VCard title="保存为模板" rounded="xl">
        <VCardText><VTextField v-model="templateName" label="模板名称" /><VTextarea v-model="templateDescription" label="模板说明" rows="3" /></VCardText>
        <VCardActions><VSpacer /><VBtn variant="text" @click="templateDialog = false">取消</VBtn><VBtn color="primary" :loading="actionLoading === 'save-template'" @click="saveTemplate">保存</VBtn></VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="importDialog" max-width="720">
      <VCard title="导入模板 JSON" rounded="xl">
        <VCardText><VTextarea v-model="importText" rows="12" label="粘贴模板 JSON" /></VCardText>
        <VCardActions><VSpacer /><VBtn variant="text" @click="importDialog = false">取消</VBtn><VBtn color="primary" @click="importTemplates">导入</VBtn></VCardActions>
      </VCard>
    </VDialog>

    <VDialog :model-value="Boolean(enlargedPoster)" max-width="620" @update:model-value="value => { if (!value) enlargedPoster = '' }">
      <VCard rounded="xl">
        <VToolbar density="comfortable" color="transparent">
          <VToolbarTitle>{{ enlargedPosterTitle }}</VToolbarTitle>
          <VBtn icon="mdi-close" variant="text" @click="enlargedPoster = ''" />
        </VToolbar>
        <VImg :src="enlargedPoster" max-height="82vh" contain class="bg-black" />
      </VCard>
    </VDialog>

    <VDialog v-model="posterDialog" max-width="620">
      <VCard rounded="xl">
        <VCardTitle class="pa-5">设置「{{ posterCollection?.name }}」合集海报</VCardTitle>
        <VDivider />
        <VCardText class="pa-5">
          <VAlert type="info" variant="tonal" class="mb-5">自动生成会使用片单中的前四张完整海报、柔化背景和渐变标题生成竖版封面；也可以上传自己的图片覆盖。</VAlert>
          <VBtn
            block
            size="large"
            color="purple"
            variant="tonal"
            prepend-icon="mdi-auto-fix"
            :loading="actionLoading === `poster-auto:${posterCollection?.id}`"
            @click="generateCollectionPoster"
          >自动生成并上传</VBtn>
          <div class="text-center text-body-2 text-medium-emphasis my-5">或上传自己的海报</div>
          <VFileInput v-model="posterFile" accept="image/jpeg,image/png,image/webp" label="选择自定义海报" prepend-icon="mdi-image-plus" show-size />
          <VBtn
            block
            color="primary"
            prepend-icon="mdi-upload"
            :disabled="!posterFile"
            :loading="actionLoading === `poster-upload:${posterCollection?.id}`"
            @click="uploadCollectionPoster"
          >上传自定义海报</VBtn>
        </VCardText>
        <VCardActions><VSpacer /><VBtn variant="text" @click="posterDialog = false">关闭</VBtn></VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.smart-page { width: 100%; max-width: 1680px; margin: 0 auto; overflow-x: hidden; }
.smart-page :deep(.v-card-title) { white-space: normal; }
.source-card { transition: transform .18s ease, border-color .18s ease; }
.source-card:hover { transform: translateY(-2px); border-color: rgb(var(--v-theme-primary)); }
.min-width-0 { min-width: 0; }
.collection-name { min-width: 230px; max-width: 360px; }
.preview-anchor { scroll-margin-top: 72px; }
.preview-table { max-height: 650px; overflow: auto; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.poster { background: rgba(var(--v-theme-on-surface), .06); }
.poster-clickable { cursor: zoom-in; transition: transform .16s ease; }
.poster-clickable:hover { transform: scale(1.08); }
.item-link { color: rgb(var(--v-theme-primary)); text-decoration: none; }
.item-link:hover { text-decoration: underline; }
.source-link { display: inline-flex; align-items: center; color: rgb(var(--v-theme-primary)); text-decoration: none; margin-top: 4px; word-break: break-all; }
.source-link:hover { text-decoration: underline; }
.emby-link { color: rgb(var(--v-theme-success)); text-decoration: none; font-weight: 600; }
.emby-link:hover { text-decoration: underline; }
@media (max-width: 700px) {
  .smart-page { padding-inline: 10px !important; }
  .page-header > div:first-child { min-width: 0; width: 100%; }
  .page-header .text-h4 { font-size: 1.75rem !important; }
  .server-chip { max-width: calc(100vw - 76px); }
  .collection-name { min-width: 100%; max-width: none; }
  .smart-page :deep(.v-card-title) { padding: 16px !important; }
  .smart-page :deep(.v-card-title .v-btn) { flex: 1 1 auto; }
}
</style>
