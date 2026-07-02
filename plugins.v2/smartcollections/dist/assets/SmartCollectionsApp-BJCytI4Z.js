import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as unwrapResponse } from './provider-DU2BtLoi.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,createBlock:_createBlock,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "smart-page pa-4 pa-md-6" };
const _hoisted_2 = {
  key: 0,
  class: "page-header d-flex flex-wrap align-center ga-3 mb-5"
};
const _hoisted_3 = { class: "source-identity d-flex align-center ga-3 flex-grow-1 min-width-0" };
const _hoisted_4 = { class: "source-name d-flex flex-column justify-center min-width-0" };
const _hoisted_5 = { class: "font-weight-medium text-truncate" };
const _hoisted_6 = { class: "text-caption text-medium-emphasis" };
const _hoisted_7 = { class: "source-actions d-flex align-center ga-2" };
const _hoisted_8 = { class: "d-flex flex-column flex-md-row ga-3" };
const _hoisted_9 = { class: "d-flex flex-wrap align-center ga-2 mb-4" };
const _hoisted_10 = { class: "text-h6" };
const _hoisted_11 = { class: "text-body-2 text-medium-emphasis mt-1" };
const _hoisted_12 = { class: "text-h5" };
const _hoisted_13 = { class: "text-h5 text-success" };
const _hoisted_14 = { class: "text-h5 text-warning" };
const _hoisted_15 = {
  key: 2,
  class: "mb-4"
};
const _hoisted_16 = { class: "d-flex justify-space-between text-body-2 mb-2" };
const _hoisted_17 = { class: "d-flex align-start ga-3" };
const _hoisted_18 = { class: "flex-grow-1" };
const _hoisted_19 = { class: "text-h6" };
const _hoisted_20 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_21 = ["href"];
const _hoisted_22 = { class: "preview-heading flex-grow-1" };
const _hoisted_23 = { class: "text-h6" };
const _hoisted_24 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_25 = ["href"];
const _hoisted_26 = { class: "preview-actions d-flex flex-wrap align-center justify-end ga-3" };
const _hoisted_27 = { class: "d-flex justify-space-between text-body-2 mb-2" };
const _hoisted_28 = { class: "text-h5" };
const _hoisted_29 = { class: "text-h5" };
const _hoisted_30 = { class: "text-h5" };
const _hoisted_31 = { class: "text-h5" };
const _hoisted_32 = { class: "preview-table" };
const _hoisted_33 = ["href"];
const _hoisted_34 = { key: 1 };
const _hoisted_35 = { class: "text-medium-emphasis" };
const _hoisted_36 = {
  key: 3,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_37 = ["href"];
const _hoisted_38 = {
  key: 1,
  class: "text-medium-emphasis"
};
const _hoisted_39 = {
  key: 2,
  class: "text-caption text-medium-emphasis"
};

const {computed,nextTick,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'SmartCollectionsApp',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'SmartCollections' },
  hideTitle: { type: Boolean, default: false },
},
  setup(__props, { expose: __expose }) {

const props = __props;

const loading = ref(false);
const actionLoading = ref('');
const error = ref('');
const notice = ref('');
const tab = ref('sources');
const sourceTab = ref('tmdb');
const status = ref({ catalog: { tmdb: [], douban: [] }, templates: [], collections: [], collection_tools: {}, history: [] });
const selectedSources = ref([]);
const manualUrl = ref('');
const preview = ref(null);
const collectionName = ref('');
const selectedPreviewKeys = ref([]);
const templateDialog = ref(false);
const templateName = ref('');
const templateDescription = ref('');
const importDialog = ref(false);
const importText = ref('');
const previewAnchor = ref(null);
const enlargedPoster = ref('');
const enlargedPosterTitle = ref('');
const subscribingKeys = ref([]);
const subscribedKeys = ref([]);
const bulkSubscriptionStatus = ref({ running: false, progress: 0, total: 0, subscribed: 0, failed: 0 });
const posterDialog = ref(false);
const posterCollection = ref(null);
const posterFile = ref(null);
const cleanupDialog = ref(false);
const cleanupConfirmed = ref(false);
const selectedBackupId = ref('');

const pluginBase = computed(() => `plugin/${props.pluginId || 'SmartCollections'}`);
const sourceItems = computed(() => status.value.catalog?.[sourceTab.value] || []);
computed(() => (preview.value?.items || []).filter(item => item.matched));
const missingSubscribableItems = computed(() => (preview.value?.items || []).filter(
  item => !item.matched && item.tmdb_id && ['movie', 'tv'].includes(item.media_type) && !subscribedKeys.value.includes(item.key),
));
const visiblePreviewItems = computed(() => (preview.value?.items || []).slice(0, 300));
const collectionTools = computed(() => status.value.collection_tools || {});
const collectionInventory = computed(() => collectionTools.value.inventory || { total: 0, managed: 0, other: 0 });
const backupOptions = computed(() => (collectionTools.value.backups || []).map(item => ({
  ...item,
  title: `${item.created_at || item.id} · ${item.collection_count || 0} 个 · ${formatBytes(item.size)}`,
})));
const allCurrentSelected = computed(() => {
  const keys = sourceItems.value.map(item => item.id);
  return keys.length > 0 && keys.every(key => selectedSources.value.includes(key))
});

function clearMessages() {
  error.value = '';
  notice.value = '';
}

function assertResponse(response) {
  if (response?.success === false) throw new Error(response.message || '操作失败')
  return unwrapResponse(response)
}

async function loadStatus() {
  loading.value = true;
  clearMessages();
  try {
    status.value = assertResponse(await props.api.get(`${pluginBase.value}/status`)) || status.value;
    bulkSubscriptionStatus.value = status.value.subscription_batch || bulkSubscriptionStatus.value;
    const backups = status.value.collection_tools?.backups || [];
    if (backups.length && !backups.some(item => item.id === selectedBackupId.value)) {
      selectedBackupId.value = backups[0].id;
    }
  } catch (err) {
    error.value = err?.message || '页面数据加载失败';
  } finally {
    loading.value = false;
  }
}

function selectAllCurrent() {
  const current = sourceItems.value.map(item => item.id);
  if (allCurrentSelected.value) {
    selectedSources.value = selectedSources.value.filter(key => !current.includes(key));
  } else {
    selectedSources.value = [...new Set([...selectedSources.value, ...current])];
  }
}

async function runPreview(source) {
  actionLoading.value = `preview:${source.id || source.template_id || source.url}`;
  clearMessages();
  try {
    const data = assertResponse(await props.api.post(`${pluginBase.value}/preview`, source));
    preview.value = data;
    collectionName.value = data.title || source.name || '';
    selectedPreviewKeys.value = (data.items || []).filter(item => item.matched).map(item => item.key);
    await nextTick();
    previewAnchor.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    error.value = err?.message || '预览失败';
  } finally {
    actionLoading.value = '';
  }
}

async function previewManual() {
  if (!manualUrl.value.trim()) {
    error.value = '请输入公开 TMDB List 或豆瓣豆列链接';
    return
  }
  await runPreview({ id: 'manual', source_type: 'manual', url: manualUrl.value.trim() });
}

async function syncPreview() {
  if (!preview.value?.preview_id) return
  actionLoading.value = 'sync-preview';
  clearMessages();
  try {
    const result = assertResponse(await props.api.post(`${pluginBase.value}/preview/sync`, {
      preview_id: preview.value.preview_id,
      name: collectionName.value.trim(),
      selected_keys: selectedPreviewKeys.value,
    }));
    await loadStatus();
    notice.value = `已同步「${result.name}」：匹配 ${result.matched}，新增 ${result.added}，移除 ${result.removed}`;
  } catch (err) {
    error.value = err?.message || '同步失败';
  } finally {
    actionLoading.value = '';
  }
}

async function batchSync() {
  const all = [...(status.value.catalog?.tmdb || []), ...(status.value.catalog?.douban || [])];
  const sources = all.filter(item => selectedSources.value.includes(item.id));
  if (!sources.length) {
    error.value = '请先选择片单';
    return
  }
  if (!window.confirm(`将依次预览并同步 ${sources.length} 个 Emby 合集，继续吗？`)) return
  actionLoading.value = 'batch-sync';
  clearMessages();
  try {
    const response = await props.api.post(`${pluginBase.value}/batch/sync`, { sources });
    const results = unwrapResponse(response) || [];
    if (response?.success === false && !results.length) throw new Error(response.message || '批量同步失败')
    const ok = results.filter(item => item.success).length;
    await loadStatus();
    notice.value = `批量同步完成：成功 ${ok} / ${results.length}`;
  } catch (err) {
    error.value = err?.message || '批量同步失败';
  } finally {
    actionLoading.value = '';
  }
}

function openTemplateDialog() {
  if (!preview.value) return
  templateName.value = collectionName.value || preview.value.title || '';
  templateDescription.value = preview.value.description || '';
  templateDialog.value = true;
}

async function saveTemplate() {
  actionLoading.value = 'save-template';
  clearMessages();
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/templates/save`, {
      preview_id: preview.value.preview_id,
      name: templateName.value,
      description: templateDescription.value,
    }));
    templateDialog.value = false;
    await loadStatus();
    notice.value = '模板已保存';
  } catch (err) {
    error.value = err?.message || '保存模板失败';
  } finally {
    actionLoading.value = '';
  }
}

async function deleteTemplate(template) {
  if (!window.confirm(`删除模板「${template.name}」？`)) return
  clearMessages();
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/templates/delete`, { template_id: template.id }));
    await loadStatus();
    notice.value = '模板已删除';
  } catch (err) {
    error.value = err?.message || '删除模板失败';
  }
}

async function exportTemplates() {
  const payload = JSON.stringify({ version: 1, templates: status.value.templates || [] }, null, 2);
  await navigator.clipboard.writeText(payload);
  notice.value = '模板 JSON 已复制到剪贴板';
}

async function importTemplates() {
  clearMessages();
  try {
    const parsed = JSON.parse(importText.value);
    const templates = Array.isArray(parsed) ? parsed : parsed.templates;
    const result = assertResponse(await props.api.post(`${pluginBase.value}/templates/import`, { templates }));
    importDialog.value = false;
    importText.value = '';
    await loadStatus();
    notice.value = `已导入 ${result.imported} 个模板`;
  } catch (err) {
    error.value = err?.message || '模板 JSON 无效';
  }
}

async function resyncCollection(collection) {
  actionLoading.value = `resync:${collection.id}`;
  clearMessages();
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/collections/resync`, { collection_id: collection.id }));
    await loadStatus();
    notice.value = `「${collection.name}」已重新同步`;
  } catch (err) {
    error.value = err?.message || '重新同步失败';
  } finally {
    actionLoading.value = '';
  }
}

async function previewCollection(collection) {
  await runPreview({
    ...(collection.source_spec || {}),
    id: `collection:${collection.id}`,
    name: collection.name,
    use_source_title: false,
  });
}

async function deleteCollection(collection) {
  if (!window.confirm(`删除「${collection.name}」的管理记录及 Emby 合集？此操作不可撤销。`)) return
  clearMessages();
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/collections/delete`, {
      collection_id: collection.id,
      delete_emby: true,
    }));
    await loadStatus();
    notice.value = '合集已删除';
  } catch (err) {
    error.value = err?.message || '删除合集失败';
  }
}

async function subscribeItem(item) {
  if (!item.tmdb_id || !item.media_type || subscribingKeys.value.includes(item.key)) return
  subscribingKeys.value = [...subscribingKeys.value, item.key];
  clearMessages();
  try {
    const response = await props.api.post(`${pluginBase.value}/subscribe`, {
      tmdb_id: item.tmdb_id,
      media_type: item.media_type,
      title: item.title,
      year: item.year,
    });
    const result = assertResponse(response) || {};
    subscribedKeys.value = [...new Set([...subscribedKeys.value, item.key])];
    notice.value = result.already_exists
      ? `「${item.title}」已经订阅，已立即搜索资源`
      : `已订阅「${item.title}」并立即搜索资源`;
  } catch (err) {
    error.value = err?.message || '添加订阅失败';
  } finally {
    subscribingKeys.value = subscribingKeys.value.filter(key => key !== item.key);
  }
}

async function waitForMissingSubscriptions() {
  for (let attempt = 0; attempt < 3600; attempt += 1) {
    const data = assertResponse(await props.api.get(`${pluginBase.value}/subscribe/missing/status`)) || {};
    bulkSubscriptionStatus.value = data;
    if (!data.running) {
      if (data.error) throw new Error(data.error)
      const keys = data.result?.subscribed_keys || [];
      subscribedKeys.value = [...new Set([...subscribedKeys.value, ...keys])];
      return data
    }
    await wait(1000);
  }
  throw new Error('一键订阅等待超时；任务可能仍在后台运行')
}

async function subscribeMissingItems() {
  const count = missingSubscribableItems.value.length;
  if (!preview.value?.preview_id || !count) return
  if (!window.confirm(`将使用 MoviePilot 默认订阅规则添加 ${count} 个缺失项目，并逐项启动搜索，继续吗？`)) return
  actionLoading.value = 'subscribe-missing';
  clearMessages();
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/subscribe/missing`, {
      preview_id: preview.value.preview_id,
    }));
    const result = await waitForMissingSubscriptions();
    notice.value = result.message || `一键订阅完成：成功 ${result.subscribed || 0}，失败 ${result.failed || 0}`;
  } catch (err) {
    error.value = err?.message || '一键订阅缺失项目失败';
  } finally {
    actionLoading.value = '';
  }
}

function showPoster(item) {
  if (!item?.poster_url) return
  enlargedPoster.value = item.poster_url;
  enlargedPosterTitle.value = item.title || '海报';
}

function openPosterManager(collection) {
  posterCollection.value = collection;
  posterFile.value = null;
  posterDialog.value = true;
}

async function generateCollectionPoster() {
  if (!posterCollection.value) return
  actionLoading.value = `poster-auto:${posterCollection.value.id}`;
  clearMessages();
  try {
    const response = await props.api.post(`${pluginBase.value}/collections/poster/auto`, {
      collection_id: posterCollection.value.id,
    });
    assertResponse(response);
    const name = posterCollection.value.name;
    posterDialog.value = false;
    await loadStatus();
    notice.value = `「${name}」合集海报已重新生成`;
  } catch (err) {
    error.value = err?.message || '自动生成海报失败';
  } finally {
    actionLoading.value = '';
  }
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('读取图片失败'));
    reader.readAsDataURL(file);
  })
}

async function uploadCollectionPoster() {
  const file = Array.isArray(posterFile.value) ? posterFile.value[0] : posterFile.value;
  if (!posterCollection.value || !file) {
    error.value = '请先选择一张海报图片';
    return
  }
  actionLoading.value = `poster-upload:${posterCollection.value.id}`;
  clearMessages();
  try {
    const image = await readFileAsDataUrl(file);
    const response = await props.api.post(`${pluginBase.value}/collections/poster/upload`, {
      collection_id: posterCollection.value.id,
      image,
    });
    assertResponse(response);
    const name = posterCollection.value.name;
    posterDialog.value = false;
    await loadStatus();
    notice.value = `「${name}」自定义海报已上传`;
  } catch (err) {
    error.value = err?.message || '上传海报失败';
  } finally {
    actionLoading.value = '';
  }
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function wait(ms) {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}

async function waitForCollectionTool() {
  for (let attempt = 0; attempt < 3600; attempt += 1) {
    const data = assertResponse(await props.api.get(`${pluginBase.value}/collections/tools/status`)) || {};
    status.value.collection_tools = data;
    if (!data.running) {
      if (data.error) throw new Error(data.error)
      await loadStatus();
      return data
    }
    await wait(1000);
  }
  throw new Error('合集任务等待超时；任务可能仍在后台运行')
}

async function startCollectionTool(action, payload = {}) {
  actionLoading.value = `collection-tool:${action}`;
  clearMessages();
  try {
    assertResponse(await props.api.post(`${pluginBase.value}/collections/tools/${action}`, payload));
    const result = await waitForCollectionTool();
    notice.value = result.message || '合集任务已完成';
  } catch (err) {
    error.value = err?.message || '合集任务执行失败';
  } finally {
    actionLoading.value = '';
  }
}

async function backupOtherCollections() {
  await startCollectionTool('backup');
}

async function restoreOtherCollections() {
  const backup = backupOptions.value.find(item => item.id === selectedBackupId.value);
  if (!backup) {
    error.value = '请先选择一个合集备份';
    return
  }
  if (!window.confirm(`从 ${backup.created_at} 的备份恢复 ${backup.collection_count} 个合集？\n恢复采用合并方式，不会删除智能合集或现有成员。`)) return
  await startCollectionTool('restore', { backup_id: backup.id });
}

function openCleanupDialog() {
  cleanupConfirmed.value = false;
  cleanupDialog.value = true;
}

async function cleanupOtherCollections() {
  cleanupDialog.value = false;
  await startCollectionTool('cleanup', { confirm_count: collectionInventory.value.other });
  cleanupConfirmed.value = false;
}

function tmdbLink(item) {
  if (!item.tmdb_id) return ''
  return `https://www.themoviedb.org/${item.media_type === 'tv' ? 'tv' : 'movie'}/${item.tmdb_id}`
}

__expose({ loadStatus, loading });
onMounted(loadStatus);

return (_ctx, _cache) => {
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VCheckboxBtn = _resolveComponent("VCheckboxBtn");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VWindow = _resolveComponent("VWindow");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VTable = _resolveComponent("VTable");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VCheckbox = _resolveComponent("VCheckbox");
  const _component_VToolbarTitle = _resolveComponent("VToolbarTitle");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VFileInput = _resolveComponent("VFileInput");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _cache[26] || (_cache[26] = _createElementVNode("div", null, [
            _createElementVNode("div", { class: "text-h4 font-weight-bold" }, "🎬 智能合集"),
            _createElementVNode("div", { class: "text-body-1 text-medium-emphasis mt-1" }, "从公开片单、豆瓣豆列或模板创建 Emby 合集，先预览，再同步。")
          ], -1)),
          _createVNode(_component_VSpacer),
          _createVNode(_component_VChip, {
            class: "server-chip",
            "prepend-icon": "mdi-server",
            variant: "tonal"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(status.value.server || '未选择 Emby'), 1)
            ]),
            _: 1
          }),
          _createVNode(_component_VBtn, {
            icon: "mdi-refresh",
            variant: "text",
            loading: loading.value,
            onClick: loadStatus
          }, null, 8, ["loading"])
        ]))
      : _createCommentVNode("", true),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "error",
          variant: "tonal",
          closable: "",
          class: "mb-4",
          "onClick:close": _cache[0] || (_cache[0] = $event => (error.value = ''))
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (notice.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 2,
          type: "success",
          variant: "tonal",
          closable: "",
          class: "mb-4",
          "onClick:close": _cache[1] || (_cache[1] = $event => (notice.value = ''))
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(notice.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (loading.value || actionLoading.value)
      ? (_openBlock(), _createBlock(_component_VProgressLinear, {
          key: 3,
          indeterminate: "",
          color: "primary",
          class: "mb-4"
        }))
      : _createCommentVNode("", true),
    _createVNode(_component_VCard, {
      rounded: "xl",
      variant: "outlined",
      class: "mb-5"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VTabs, {
          modelValue: tab.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((tab).value = $event)),
          color: "primary",
          grow: ""
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VTab, {
              value: "sources",
              "prepend-icon": "mdi-format-list-checks"
            }, {
              default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                _createTextVNode("片单与模板", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VTab, {
              value: "templates",
              "prepend-icon": "mdi-bookmark-box-multiple"
            }, {
              default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                _createTextVNode("我的模板", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VTab, {
              value: "collections",
              "prepend-icon": "mdi-folder-star-multiple"
            }, {
              default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                _createTextVNode("已同步合集", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"])
      ]),
      _: 1
    }),
    _createVNode(_component_VWindow, {
      modelValue: tab.value,
      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((tab).value = $event))
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VWindowItem, { value: "sources" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCard, {
              rounded: "xl",
              variant: "outlined",
              class: "mb-5"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "d-flex flex-wrap align-center ga-2 pa-5" }, {
                  default: _withCtx(() => [
                    _cache[30] || (_cache[30] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "text-h6" }, "片单目录"),
                      _createElementVNode("div", { class: "text-body-2 text-medium-emphasis" }, "选择一个预览，或多选后批量同步。")
                    ], -1)),
                    _createVNode(_component_VSpacer),
                    _createVNode(_component_VBtn, {
                      variant: "text",
                      "prepend-icon": "mdi-select-all",
                      onClick: selectAllCurrent
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(allCurrentSelected.value ? '取消本页全选' : '本页全选'), 1)
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      "prepend-icon": "mdi-sync",
                      loading: actionLoading.value === 'batch-sync',
                      onClick: batchSync
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode("批量同步（" + _toDisplayString(selectedSources.value.length) + "）", 1)
                      ]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VDivider),
                _createVNode(_component_VCardText, { class: "pa-5" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTabs, {
                      modelValue: sourceTab.value,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((sourceTab).value = $event)),
                      density: "comfortable",
                      color: "primary",
                      class: "mb-4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTab, { value: "tmdb" }, {
                          default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                            _createTextVNode("TMDB 公开片单", -1)
                          ]))]),
                          _: 1
                        }),
                        _createVNode(_component_VTab, { value: "douban" }, {
                          default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                            _createTextVNode("热门豆列", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"]),
                    _createVNode(_component_VRow, { dense: "" }, {
                      default: _withCtx(() => [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sourceItems.value, (source) => {
                          return (_openBlock(), _createBlock(_component_VCol, {
                            key: source.id,
                            cols: "12",
                            lg: "6"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VCard, {
                                rounded: "lg",
                                variant: "outlined",
                                class: "source-card h-100"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VCardText, { class: "source-row d-flex align-center ga-3 pa-3" }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VCheckboxBtn, {
                                        modelValue: selectedSources.value,
                                        "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((selectedSources).value = $event)),
                                        value: source.id,
                                        color: "primary",
                                        class: "source-check"
                                      }, null, 8, ["modelValue", "value"]),
                                      _createElementVNode("div", _hoisted_3, [
                                        _createVNode(_component_VAvatar, {
                                          color: sourceTab.value === 'douban' ? 'green' : 'blue',
                                          variant: "tonal",
                                          rounded: "lg",
                                          size: "42",
                                          class: "source-avatar"
                                        }, {
                                          default: _withCtx(() => [
                                            _createVNode(_component_VIcon, {
                                              icon: sourceTab.value === 'douban' ? 'mdi-alpha-d-box' : 'mdi-movie-open-star'
                                            }, null, 8, ["icon"])
                                          ]),
                                          _: 1
                                        }, 8, ["color"]),
                                        _createElementVNode("div", _hoisted_4, [
                                          _createElementVNode("div", _hoisted_5, _toDisplayString(source.name), 1),
                                          _createElementVNode("div", _hoisted_6, _toDisplayString(sourceTab.value === 'douban' ? `豆列 ${source.list_id}` : source.media_type === 'tv' ? '剧集片单' : '电影片单'), 1)
                                        ])
                                      ]),
                                      _createElementVNode("div", _hoisted_7, [
                                        (source.url)
                                          ? (_openBlock(), _createBlock(_component_VBtn, {
                                              key: 0,
                                              href: source.url,
                                              target: "_blank",
                                              rel: "noopener",
                                              size: "small",
                                              variant: "text",
                                              "prepend-icon": "mdi-open-in-new"
                                            }, {
                                              default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                                                _createTextVNode("来源", -1)
                                              ]))]),
                                              _: 1
                                            }, 8, ["href"]))
                                          : _createCommentVNode("", true),
                                        _createVNode(_component_VBtn, {
                                          size: "small",
                                          variant: "tonal",
                                          "prepend-icon": "mdi-eye",
                                          loading: actionLoading.value === `preview:${source.id}`,
                                          onClick: $event => (runPreview(source))
                                        }, {
                                          default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                                            _createTextVNode("预览匹配", -1)
                                          ]))]),
                                          _: 1
                                        }, 8, ["loading", "onClick"])
                                      ])
                                    ]),
                                    _: 2
                                  }, 1024)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024))
                        }), 128))
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCard, {
              rounded: "xl",
              variant: "outlined",
              class: "mb-5"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardText, { class: "pa-5" }, {
                  default: _withCtx(() => [
                    _cache[36] || (_cache[36] = _createElementVNode("div", { class: "text-h6 mb-1" }, "手动输入公开片单", -1)),
                    _cache[37] || (_cache[37] = _createElementVNode("div", { class: "text-body-2 text-medium-emphasis mb-4" }, "支持 TMDB List 和豆瓣豆列链接。", -1)),
                    _createElementVNode("div", _hoisted_8, [
                      _createVNode(_component_VTextField, {
                        modelValue: manualUrl.value,
                        "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((manualUrl).value = $event)),
                        label: "片单链接",
                        placeholder: "https://www.themoviedb.org/list/... 或 https://www.douban.com/doulist/.../",
                        "hide-details": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        size: "large",
                        "prepend-icon": "mdi-eye",
                        loading: actionLoading.value === 'preview:manual',
                        onClick: previewManual
                      }, {
                        default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                          _createTextVNode("预览匹配", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading"])
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VWindowItem, { value: "templates" }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_9, [
              _cache[40] || (_cache[40] = _createElementVNode("div", null, [
                _createElementVNode("div", { class: "text-h6" }, "我的模板"),
                _createElementVNode("div", { class: "text-body-2 text-medium-emphasis" }, "模板保存的是已解析的 TMDB 条目，可导入导出。")
              ], -1)),
              _createVNode(_component_VSpacer),
              _createVNode(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-export",
                disabled: !status.value.templates?.length,
                onClick: exportTemplates
              }, {
                default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                  _createTextVNode("导出全部", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"]),
              _createVNode(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-import",
                onClick: _cache[6] || (_cache[6] = $event => (importDialog.value = true))
              }, {
                default: _withCtx(() => [...(_cache[39] || (_cache[39] = [
                  _createTextVNode("导入模板", -1)
                ]))]),
                _: 1
              })
            ]),
            (status.value.templates?.length)
              ? (_openBlock(), _createBlock(_component_VRow, { key: 0 }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(status.value.templates, (template) => {
                      return (_openBlock(), _createBlock(_component_VCol, {
                        key: template.id,
                        cols: "12",
                        md: "6",
                        lg: "4"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCard, {
                            rounded: "xl",
                            variant: "outlined",
                            class: "h-100"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VCardText, null, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VAvatar, {
                                    color: "purple",
                                    variant: "tonal",
                                    rounded: "lg",
                                    class: "mb-3"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VIcon, { icon: "mdi-bookmark-star" })
                                    ]),
                                    _: 1
                                  }),
                                  _createElementVNode("div", _hoisted_10, _toDisplayString(template.name), 1),
                                  _createElementVNode("div", _hoisted_11, _toDisplayString(template.description || '自定义智能合集模板'), 1),
                                  _createVNode(_component_VChip, {
                                    size: "small",
                                    class: "mt-3"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(template.item_count || template.items?.length || 0) + " 个条目", 1)
                                    ]),
                                    _: 2
                                  }, 1024)
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VCardActions, null, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VBtn, {
                                    color: "primary",
                                    variant: "tonal",
                                    "prepend-icon": "mdi-eye",
                                    onClick: $event => (runPreview({ template_id: template.id, id: template.id }))
                                  }, {
                                    default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
                                      _createTextVNode("预览", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["onClick"]),
                                  _createVNode(_component_VSpacer),
                                  _createVNode(_component_VBtn, {
                                    icon: "mdi-delete-outline",
                                    color: "error",
                                    variant: "text",
                                    onClick: $event => (deleteTemplate(template))
                                  }, null, 8, ["onClick"])
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128))
                  ]),
                  _: 1
                }))
              : (_openBlock(), _createBlock(_component_VAlert, {
                  key: 1,
                  type: "info",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
                    _createTextVNode("预览任意片单后，可将结果保存为模板。", -1)
                  ]))]),
                  _: 1
                }))
          ]),
          _: 1
        }),
        _createVNode(_component_VWindowItem, { value: "collections" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCard, {
              rounded: "xl",
              variant: "outlined",
              class: "mb-5 collection-tools-card"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "d-flex flex-wrap align-center ga-3 pa-5" }, {
                  default: _withCtx(() => [
                    _cache[44] || (_cache[44] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "text-h6" }, "Emby 其他合集管理"),
                      _createElementVNode("div", { class: "text-body-2 text-medium-emphasis" }, "“其他合集”指未由智能合集管理的 Emby 合集；操作始终保留智能合集。")
                    ], -1)),
                    _createVNode(_component_VSpacer),
                    _createVNode(_component_VChip, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-shield-check"
                    }, {
                      default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                        _createTextVNode("安全备份优先", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VDivider),
                _createVNode(_component_VCardText, { class: "pa-5" }, {
                  default: _withCtx(() => [
                    (collectionTools.value.available === false)
                      ? (_openBlock(), _createBlock(_component_VAlert, {
                          key: 0,
                          type: "warning",
                          variant: "tonal",
                          class: "mb-4"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(collectionTools.value.inventory_error || '暂时无法读取 Emby 合集'), 1)
                          ]),
                          _: 1
                        }))
                      : (_openBlock(), _createBlock(_component_VRow, {
                          key: 1,
                          class: "mb-2"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VCol, { cols: "4" }, {
                              default: _withCtx(() => [
                                _cache[45] || (_cache[45] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "全部合集", -1)),
                                _createElementVNode("div", _hoisted_12, _toDisplayString(collectionInventory.value.total), 1)
                              ]),
                              _: 1
                            }),
                            _createVNode(_component_VCol, { cols: "4" }, {
                              default: _withCtx(() => [
                                _cache[46] || (_cache[46] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "智能合集", -1)),
                                _createElementVNode("div", _hoisted_13, _toDisplayString(collectionInventory.value.managed), 1)
                              ]),
                              _: 1
                            }),
                            _createVNode(_component_VCol, { cols: "4" }, {
                              default: _withCtx(() => [
                                _cache[47] || (_cache[47] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "其他合集", -1)),
                                _createElementVNode("div", _hoisted_14, _toDisplayString(collectionInventory.value.other), 1)
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })),
                    _createVNode(_component_VAlert, {
                      type: "info",
                      variant: "tonal",
                      class: "mb-4"
                    }, {
                      default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                        _createTextVNode(" 备份包含合集名称、简介、外部 ID、成员和压缩主海报，保留最近 5 份。恢复只合并缺失内容，不移除现有成员。 ", -1)
                      ]))]),
                      _: 1
                    }),
                    (collectionTools.value.running)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_15, [
                          _createElementVNode("div", _hoisted_16, [
                            _createElementVNode("span", null, _toDisplayString(collectionTools.value.message), 1),
                            _createElementVNode("span", null, _toDisplayString(collectionTools.value.progress || 0) + "%", 1)
                          ]),
                          _createVNode(_component_VProgressLinear, {
                            "model-value": collectionTools.value.progress || 0,
                            color: "primary",
                            rounded: "",
                            height: "8"
                          }, null, 8, ["model-value"])
                        ]))
                      : _createCommentVNode("", true),
                    _createVNode(_component_VSelect, {
                      modelValue: selectedBackupId.value,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((selectedBackupId).value = $event)),
                      items: backupOptions.value,
                      "item-title": "title",
                      "item-value": "id",
                      label: "选择要恢复的本地备份",
                      disabled: !backupOptions.value.length || collectionTools.value.running,
                      "hide-details": ""
                    }, null, 8, ["modelValue", "items", "disabled"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardActions, { class: "flex-wrap px-5 pb-5" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-content-save-outline",
                      disabled: collectionTools.value.running || collectionInventory.value.other < 1,
                      loading: actionLoading.value === 'collection-tool:backup',
                      onClick: backupOtherCollections
                    }, {
                      default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
                        _createTextVNode("备份其他合集", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled", "loading"]),
                    _createVNode(_component_VBtn, {
                      color: "success",
                      variant: "tonal",
                      "prepend-icon": "mdi-backup-restore",
                      disabled: collectionTools.value.running || !selectedBackupId.value,
                      loading: actionLoading.value === 'collection-tool:restore',
                      onClick: restoreOtherCollections
                    }, {
                      default: _withCtx(() => [...(_cache[50] || (_cache[50] = [
                        _createTextVNode("恢复所选备份", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled", "loading"]),
                    _createVNode(_component_VSpacer),
                    _createVNode(_component_VBtn, {
                      color: "error",
                      variant: "tonal",
                      "prepend-icon": "mdi-delete-sweep-outline",
                      disabled: collectionTools.value.running || collectionInventory.value.other < 1,
                      loading: actionLoading.value === 'collection-tool:cleanup',
                      onClick: openCleanupDialog
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode("清理其他合集（" + _toDisplayString(collectionInventory.value.other) + "）", 1)
                      ]),
                      _: 1
                    }, 8, ["disabled", "loading"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _cache[57] || (_cache[57] = _createElementVNode("div", { class: "text-h6 mb-1" }, "已同步合集", -1)),
            _cache[58] || (_cache[58] = _createElementVNode("div", { class: "text-body-2 text-medium-emphasis mb-4" }, "重新同步来源，或同时删除管理记录和 Emby 合集。", -1)),
            (status.value.collections?.length)
              ? (_openBlock(), _createBlock(_component_VRow, { key: 0 }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(status.value.collections, (collection) => {
                      return (_openBlock(), _createBlock(_component_VCol, {
                        key: collection.id,
                        cols: "12",
                        md: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCard, {
                            rounded: "xl",
                            variant: "outlined"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VCardText, null, {
                                default: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_17, [
                                    _createVNode(_component_VAvatar, {
                                      color: "green",
                                      variant: "tonal",
                                      rounded: "lg"
                                    }, {
                                      default: _withCtx(() => [
                                        _createVNode(_component_VIcon, { icon: "mdi-folder-star" })
                                      ]),
                                      _: 1
                                    }),
                                    _createElementVNode("div", _hoisted_18, [
                                      _createElementVNode("div", _hoisted_19, _toDisplayString(collection.name), 1),
                                      _createElementVNode("div", _hoisted_20, _toDisplayString(collection.source) + " · 最近同步 " + _toDisplayString(collection.last_sync_at), 1),
                                      (collection.source_url)
                                        ? (_openBlock(), _createElementBlock("a", {
                                            key: 0,
                                            href: collection.source_url,
                                            target: "_blank",
                                            rel: "noopener",
                                            class: "source-link text-caption"
                                          }, [
                                            _createVNode(_component_VIcon, {
                                              icon: "mdi-link-variant",
                                              size: "small",
                                              class: "me-1"
                                            }),
                                            _cache[51] || (_cache[51] = _createTextVNode("查看片单来源 ", -1))
                                          ], 8, _hoisted_21))
                                        : _createCommentVNode("", true)
                                    ]),
                                    _createVNode(_component_VChip, {
                                      color: "success",
                                      variant: "tonal"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(collection.matched_count) + "/" + _toDisplayString(collection.total_count), 1)
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ]),
                                  (collection.poster_source)
                                    ? (_openBlock(), _createBlock(_component_VChip, {
                                        key: 0,
                                        size: "small",
                                        variant: "tonal",
                                        color: "purple",
                                        class: "mt-3"
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(collection.poster_source === 'custom' ? '自定义海报' : '自动海报'), 1)
                                        ]),
                                        _: 2
                                      }, 1024))
                                    : _createCommentVNode("", true)
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VCardActions, { class: "flex-wrap" }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VBtn, {
                                    variant: "tonal",
                                    "prepend-icon": "mdi-sync",
                                    loading: actionLoading.value === `resync:${collection.id}`,
                                    onClick: $event => (resyncCollection(collection))
                                  }, {
                                    default: _withCtx(() => [...(_cache[52] || (_cache[52] = [
                                      _createTextVNode("重新同步", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["loading", "onClick"]),
                                  _createVNode(_component_VBtn, {
                                    variant: "tonal",
                                    "prepend-icon": "mdi-eye",
                                    loading: actionLoading.value === `preview:collection:${collection.id}`,
                                    onClick: $event => (previewCollection(collection))
                                  }, {
                                    default: _withCtx(() => [...(_cache[53] || (_cache[53] = [
                                      _createTextVNode("预览匹配", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["loading", "onClick"]),
                                  _createVNode(_component_VBtn, {
                                    variant: "tonal",
                                    "prepend-icon": "mdi-image-edit",
                                    onClick: $event => (openPosterManager(collection))
                                  }, {
                                    default: _withCtx(() => [...(_cache[54] || (_cache[54] = [
                                      _createTextVNode("海报", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["onClick"]),
                                  _createVNode(_component_VSpacer),
                                  _createVNode(_component_VBtn, {
                                    color: "error",
                                    variant: "text",
                                    "prepend-icon": "mdi-delete-outline",
                                    onClick: $event => (deleteCollection(collection))
                                  }, {
                                    default: _withCtx(() => [...(_cache[55] || (_cache[55] = [
                                      _createTextVNode("删除", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["onClick"])
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128))
                  ]),
                  _: 1
                }))
              : (_openBlock(), _createBlock(_component_VAlert, {
                  key: 1,
                  type: "info",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [...(_cache[56] || (_cache[56] = [
                    _createTextVNode("还没有由本插件同步并管理的 Emby 合集。", -1)
                  ]))]),
                  _: 1
                }))
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    (preview.value)
      ? (_openBlock(), _createElementBlock("div", {
          key: 4,
          ref_key: "previewAnchor",
          ref: previewAnchor,
          class: "preview-anchor pt-2"
        }, [
          _createVNode(_component_VCard, {
            rounded: "xl",
            variant: "outlined",
            class: "mt-4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardTitle, { class: "preview-header d-flex flex-wrap align-center ga-3 pa-5" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_22, [
                    _createElementVNode("div", _hoisted_23, _toDisplayString(preview.value.title), 1),
                    _createElementVNode("div", _hoisted_24, "共 " + _toDisplayString(preview.value.total_count) + " · 电影 " + _toDisplayString(preview.value.movie_count) + " · 剧集 " + _toDisplayString(preview.value.tv_count) + " · Emby 已有 " + _toDisplayString(preview.value.matched_count) + " · 缺失 " + _toDisplayString(preview.value.missing_count), 1),
                    (preview.value.source_url)
                      ? (_openBlock(), _createElementBlock("a", {
                          key: 0,
                          href: preview.value.source_url,
                          target: "_blank",
                          rel: "noopener",
                          class: "source-link text-caption"
                        }, [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-open-in-new",
                            size: "small",
                            class: "me-1"
                          }),
                          _createTextVNode(_toDisplayString(preview.value.source_url), 1)
                        ], 8, _hoisted_25))
                      : _createCommentVNode("", true)
                  ]),
                  _createElementVNode("div", _hoisted_26, [
                    _createVNode(_component_VTextField, {
                      modelValue: collectionName.value,
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((collectionName).value = $event)),
                      label: "合集名称",
                      density: "compact",
                      "hide-details": "",
                      class: "collection-name"
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VBtn, {
                      color: "warning",
                      variant: "tonal",
                      "prepend-icon": "mdi-bell-plus-outline",
                      disabled: !missingSubscribableItems.value.length || bulkSubscriptionStatus.value.running,
                      loading: actionLoading.value === 'subscribe-missing',
                      onClick: subscribeMissingItems
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode("一键订阅缺失项目（" + _toDisplayString(missingSubscribableItems.value.length) + "）", 1)
                      ]),
                      _: 1
                    }, 8, ["disabled", "loading"]),
                    _createVNode(_component_VBtn, {
                      color: "success",
                      "prepend-icon": "mdi-folder-plus",
                      disabled: !selectedPreviewKeys.value.length,
                      loading: actionLoading.value === 'sync-preview',
                      onClick: syncPreview
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode("同步至 Emby（" + _toDisplayString(selectedPreviewKeys.value.length) + "）", 1)
                      ]),
                      _: 1
                    }, 8, ["disabled", "loading"]),
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-bookmark-plus",
                      onClick: openTemplateDialog
                    }, {
                      default: _withCtx(() => [...(_cache[59] || (_cache[59] = [
                        _createTextVNode("保存为模板", -1)
                      ]))]),
                      _: 1
                    })
                  ])
                ]),
                _: 1
              }),
              _createVNode(_component_VDivider),
              _createVNode(_component_VCardText, { class: "pa-4" }, {
                default: _withCtx(() => [
                  (bulkSubscriptionStatus.value.running)
                    ? (_openBlock(), _createBlock(_component_VAlert, {
                        key: 0,
                        type: "info",
                        variant: "tonal",
                        class: "mb-3"
                      }, {
                        default: _withCtx(() => [
                          _createElementVNode("div", _hoisted_27, [
                            _createElementVNode("span", null, _toDisplayString(bulkSubscriptionStatus.value.message), 1),
                            _createElementVNode("span", null, _toDisplayString(bulkSubscriptionStatus.value.progress || 0) + "%", 1)
                          ]),
                          _createVNode(_component_VProgressLinear, {
                            "model-value": bulkSubscriptionStatus.value.progress || 0,
                            color: "primary",
                            rounded: "",
                            height: "7"
                          }, null, 8, ["model-value"])
                        ]),
                        _: 1
                      }))
                    : _createCommentVNode("", true),
                  _createVNode(_component_VRow, { class: "mb-3" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VCol, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCard, {
                            color: "blue",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VCardText, null, {
                                default: _withCtx(() => [
                                  _cache[60] || (_cache[60] = _createElementVNode("div", { class: "text-caption" }, "列表总数", -1)),
                                  _createElementVNode("div", _hoisted_28, _toDisplayString(preview.value.total_count), 1)
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VCol, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCard, {
                            color: "cyan",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VCardText, null, {
                                default: _withCtx(() => [
                                  _cache[61] || (_cache[61] = _createElementVNode("div", { class: "text-caption" }, "电影 / 剧集", -1)),
                                  _createElementVNode("div", _hoisted_29, _toDisplayString(preview.value.movie_count) + " / " + _toDisplayString(preview.value.tv_count), 1)
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VCol, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCard, {
                            color: "success",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VCardText, null, {
                                default: _withCtx(() => [
                                  _cache[62] || (_cache[62] = _createElementVNode("div", { class: "text-caption" }, "已匹配", -1)),
                                  _createElementVNode("div", _hoisted_30, _toDisplayString(preview.value.matched_count), 1)
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VCol, {
                        cols: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCard, {
                            color: "warning",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VCardText, null, {
                                default: _withCtx(() => [
                                  _cache[63] || (_cache[63] = _createElementVNode("div", { class: "text-caption" }, "缺失", -1)),
                                  _createElementVNode("div", _hoisted_31, _toDisplayString(preview.value.missing_count), 1)
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createElementVNode("div", _hoisted_32, [
                    _createVNode(_component_VTable, {
                      hover: "",
                      density: "comfortable"
                    }, {
                      default: _withCtx(() => [
                        _cache[64] || (_cache[64] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th"),
                            _createElementVNode("th", null, "#"),
                            _createElementVNode("th", null, "海报"),
                            _createElementVNode("th", null, "状态"),
                            _createElementVNode("th", null, "标题"),
                            _createElementVNode("th", null, "Emby 匹配")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(visiblePreviewItems.value, (item) => {
                            return (_openBlock(), _createElementBlock("tr", {
                              key: item.key
                            }, [
                              _createElementVNode("td", null, [
                                (item.matched)
                                  ? (_openBlock(), _createBlock(_component_VCheckboxBtn, {
                                      key: 0,
                                      modelValue: selectedPreviewKeys.value,
                                      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((selectedPreviewKeys).value = $event)),
                                      value: item.key,
                                      color: "success"
                                    }, null, 8, ["modelValue", "value"]))
                                  : _createCommentVNode("", true)
                              ]),
                              _createElementVNode("td", null, _toDisplayString(item.position), 1),
                              _createElementVNode("td", null, [
                                _createVNode(_component_VImg, {
                                  src: item.poster_url,
                                  width: "42",
                                  height: "62",
                                  cover: "",
                                  class: _normalizeClass(['poster', 'rounded', { 'poster-clickable': item.poster_url }]),
                                  onClick: $event => (showPoster(item))
                                }, null, 8, ["src", "class", "onClick"])
                              ]),
                              _createElementVNode("td", null, [
                                _createVNode(_component_VChip, {
                                  color: item.matched ? 'success' : 'default',
                                  size: "small",
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.matched ? '已匹配' : '缺失'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"])
                              ]),
                              _createElementVNode("td", null, [
                                (tmdbLink(item))
                                  ? (_openBlock(), _createElementBlock("a", {
                                      key: 0,
                                      href: tmdbLink(item),
                                      target: "_blank",
                                      class: "item-link"
                                    }, _toDisplayString(item.title), 9, _hoisted_33))
                                  : (_openBlock(), _createElementBlock("span", _hoisted_34, _toDisplayString(item.title), 1)),
                                _createElementVNode("span", _hoisted_35, _toDisplayString(item.year ? `(${item.year})` : ''), 1),
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  class: "ms-2"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.media_type === 'tv' ? '剧集' : '电影'), 1)
                                  ]),
                                  _: 2
                                }, 1024),
                                (!item.matched && item.tmdb_id)
                                  ? (_openBlock(), _createBlock(_component_VBtn, {
                                      key: 2,
                                      size: "x-small",
                                      color: "primary",
                                      variant: "tonal",
                                      class: "ms-2",
                                      "prepend-icon": "mdi-bell-plus-outline",
                                      loading: subscribingKeys.value.includes(item.key),
                                      disabled: subscribedKeys.value.includes(item.key),
                                      onClick: $event => (subscribeItem(item))
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(subscribedKeys.value.includes(item.key) ? '已订阅' : '订阅'), 1)
                                      ]),
                                      _: 2
                                    }, 1032, ["loading", "disabled", "onClick"]))
                                  : _createCommentVNode("", true),
                                (!item.matched)
                                  ? (_openBlock(), _createElementBlock("div", _hoisted_36, _toDisplayString(item.missing_reason), 1))
                                  : _createCommentVNode("", true)
                              ]),
                              _createElementVNode("td", null, [
                                (item.emby_url)
                                  ? (_openBlock(), _createElementBlock("a", {
                                      key: 0,
                                      href: item.emby_url,
                                      target: "_blank",
                                      rel: "noopener",
                                      class: "emby-link"
                                    }, _toDisplayString(item.emby_name), 9, _hoisted_37))
                                  : (_openBlock(), _createElementBlock("span", _hoisted_38, _toDisplayString(item.emby_name || '—'), 1)),
                                (item.match_method === 'title')
                                  ? (_openBlock(), _createElementBlock("span", _hoisted_39, "（标题兜底）"))
                                  : _createCommentVNode("", true)
                              ])
                            ]))
                          }), 128))
                        ])
                      ]),
                      _: 1
                    })
                  ]),
                  (preview.value.items?.length > 300)
                    ? (_openBlock(), _createBlock(_component_VAlert, {
                        key: 1,
                        type: "info",
                        variant: "tonal",
                        class: "mt-3"
                      }, {
                        default: _withCtx(() => [...(_cache[65] || (_cache[65] = [
                          _createTextVNode("页面只展示前 300 条；同步仍会处理全部条目。", -1)
                        ]))]),
                        _: 1
                      }))
                    : _createCommentVNode("", true)
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ], 512))
      : _createCommentVNode("", true),
    _createVNode(_component_VDialog, {
      modelValue: templateDialog.value,
      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((templateDialog).value = $event)),
      "max-width": "560"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, {
          title: "保存为模板",
          rounded: "xl"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createVNode(_component_VTextField, {
                  modelValue: templateName.value,
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((templateName).value = $event)),
                  label: "模板名称"
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextarea, {
                  modelValue: templateDescription.value,
                  "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((templateDescription).value = $event)),
                  label: "模板说明",
                  rows: "3"
                }, null, 8, ["modelValue"])
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[13] || (_cache[13] = $event => (templateDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[66] || (_cache[66] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  loading: actionLoading.value === 'save-template',
                  onClick: saveTemplate
                }, {
                  default: _withCtx(() => [...(_cache[67] || (_cache[67] = [
                    _createTextVNode("保存", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: importDialog.value,
      "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((importDialog).value = $event)),
      "max-width": "720"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, {
          title: "导入模板 JSON",
          rounded: "xl"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createVNode(_component_VTextarea, {
                  modelValue: importText.value,
                  "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((importText).value = $event)),
                  rows: "12",
                  label: "粘贴模板 JSON"
                }, null, 8, ["modelValue"])
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[16] || (_cache[16] = $event => (importDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[68] || (_cache[68] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  onClick: importTemplates
                }, {
                  default: _withCtx(() => [...(_cache[69] || (_cache[69] = [
                    _createTextVNode("导入", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: cleanupDialog.value,
      "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((cleanupDialog).value = $event)),
      "max-width": "620",
      persistent: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { rounded: "xl" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "pa-5 text-error" }, {
              default: _withCtx(() => [...(_cache[70] || (_cache[70] = [
                _createTextVNode("确认清理其他 Emby 合集", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, { class: "pa-5" }, {
              default: _withCtx(() => [
                _createVNode(_component_VAlert, {
                  type: "error",
                  variant: "tonal",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 将清理 " + _toDisplayString(collectionInventory.value.other) + " 个非智能合集。插件会先创建一份包含成员和海报的新备份；智能合集不会被删除。 ", 1)
                  ]),
                  _: 1
                }),
                _cache[71] || (_cache[71] = _createElementVNode("div", { class: "text-body-2 text-medium-emphasis mb-3" }, "恢复入口会一直保留在“Emby 其他合集管理”中，默认使用合并恢复。", -1)),
                _createVNode(_component_VCheckbox, {
                  modelValue: cleanupConfirmed.value,
                  "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((cleanupConfirmed).value = $event)),
                  color: "error",
                  label: "我已理解操作范围，并确认先自动备份再清理",
                  "hide-details": ""
                }, null, 8, ["modelValue"])
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, { class: "px-5 pb-5" }, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[19] || (_cache[19] = $event => (cleanupDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[72] || (_cache[72] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "error",
                  disabled: !cleanupConfirmed.value,
                  "prepend-icon": "mdi-delete-sweep",
                  onClick: cleanupOtherCollections
                }, {
                  default: _withCtx(() => [...(_cache[73] || (_cache[73] = [
                    _createTextVNode("自动备份并清理", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      "model-value": Boolean(enlargedPoster.value),
      "max-width": "620",
      "onUpdate:modelValue": _cache[22] || (_cache[22] = value => { if (!value) enlargedPoster.value = ''; })
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { rounded: "xl" }, {
          default: _withCtx(() => [
            _createVNode(_component_VToolbar, {
              density: "comfortable",
              color: "transparent"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VToolbarTitle, null, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(enlargedPosterTitle.value), 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[21] || (_cache[21] = $event => (enlargedPoster.value = ''))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VImg, {
              src: enlargedPoster.value,
              "max-height": "82vh",
              contain: "",
              class: "bg-black"
            }, null, 8, ["src"])
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["model-value"]),
    _createVNode(_component_VDialog, {
      modelValue: posterDialog.value,
      "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((posterDialog).value = $event)),
      "max-width": "620"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { rounded: "xl" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "pa-5" }, {
              default: _withCtx(() => [
                _createTextVNode("设置「" + _toDisplayString(posterCollection.value?.name) + "」合集海报", 1)
              ]),
              _: 1
            }),
            _createVNode(_component_VDivider),
            _createVNode(_component_VCardText, { class: "pa-5" }, {
              default: _withCtx(() => [
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  class: "mb-5"
                }, {
                  default: _withCtx(() => [...(_cache[74] || (_cache[74] = [
                    _createTextVNode("自动生成会使用片单中的多张海报组成倾斜海报墙，并叠加由下向上的浅色渐变与自适应标题；也可以上传自己的图片覆盖。", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  block: "",
                  size: "large",
                  color: "purple",
                  variant: "tonal",
                  "prepend-icon": "mdi-auto-fix",
                  loading: actionLoading.value === `poster-auto:${posterCollection.value?.id}`,
                  onClick: generateCollectionPoster
                }, {
                  default: _withCtx(() => [...(_cache[75] || (_cache[75] = [
                    _createTextVNode("自动生成并上传", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"]),
                _cache[77] || (_cache[77] = _createElementVNode("div", { class: "text-center text-body-2 text-medium-emphasis my-5" }, "或上传自己的海报", -1)),
                _createVNode(_component_VFileInput, {
                  modelValue: posterFile.value,
                  "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((posterFile).value = $event)),
                  accept: "image/jpeg,image/png,image/webp",
                  label: "选择自定义海报",
                  "prepend-icon": "mdi-image-plus",
                  "show-size": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VBtn, {
                  block: "",
                  color: "primary",
                  "prepend-icon": "mdi-upload",
                  disabled: !posterFile.value,
                  loading: actionLoading.value === `poster-upload:${posterCollection.value?.id}`,
                  onClick: uploadCollectionPoster
                }, {
                  default: _withCtx(() => [...(_cache[76] || (_cache[76] = [
                    _createTextVNode("上传自定义海报", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"])
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[24] || (_cache[24] = $event => (posterDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[78] || (_cache[78] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const SmartCollectionsApp = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-4695722c"]]);

export { SmartCollectionsApp as S, _export_sfc as _ };
