import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as unwrapResponse } from './provider-8rizRzPF.js';

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
const _hoisted_3 = { class: "flex-grow-1 min-width-0" };
const _hoisted_4 = { class: "font-weight-medium text-truncate" };
const _hoisted_5 = { class: "text-caption text-medium-emphasis mt-1" };
const _hoisted_6 = { class: "d-flex flex-column flex-md-row ga-3" };
const _hoisted_7 = { class: "d-flex flex-wrap align-center ga-2 mb-4" };
const _hoisted_8 = { class: "text-h6" };
const _hoisted_9 = { class: "text-body-2 text-medium-emphasis mt-1" };
const _hoisted_10 = { class: "d-flex align-start ga-3" };
const _hoisted_11 = { class: "flex-grow-1" };
const _hoisted_12 = { class: "text-h6" };
const _hoisted_13 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_14 = { class: "flex-grow-1" };
const _hoisted_15 = { class: "text-h6" };
const _hoisted_16 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_17 = { class: "text-h5" };
const _hoisted_18 = { class: "text-h5" };
const _hoisted_19 = { class: "text-h5" };
const _hoisted_20 = { class: "text-h5" };
const _hoisted_21 = { class: "preview-table" };
const _hoisted_22 = ["href"];
const _hoisted_23 = { key: 1 };
const _hoisted_24 = { class: "text-medium-emphasis" };
const _hoisted_25 = {
  key: 2,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_26 = {
  key: 0,
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
const status = ref({ catalog: { tmdb: [], douban: [] }, templates: [], collections: [], history: [] });
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

const pluginBase = computed(() => `plugin/${props.pluginId || 'SmartCollections'}`);
const sourceItems = computed(() => status.value.catalog?.[sourceTab.value] || []);
computed(() => (preview.value?.items || []).filter(item => item.matched));
const visiblePreviewItems = computed(() => (preview.value?.items || []).slice(0, 300));
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
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
  const _component_VWindow = _resolveComponent("VWindow");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VTable = _resolveComponent("VTable");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _cache[17] || (_cache[17] = _createElementVNode("div", null, [
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
              default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
                _createTextVNode("片单与模板", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VTab, {
              value: "templates",
              "prepend-icon": "mdi-bookmark-box-multiple"
            }, {
              default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                _createTextVNode("我的模板", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VTab, {
              value: "collections",
              "prepend-icon": "mdi-folder-star-multiple"
            }, {
              default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
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
      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((tab).value = $event))
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
                    _cache[21] || (_cache[21] = _createElementVNode("div", null, [
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
                          default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                            _createTextVNode("TMDB 公开片单", -1)
                          ]))]),
                          _: 1
                        }),
                        _createVNode(_component_VTab, { value: "douban" }, {
                          default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                            _createTextVNode("热门豆列", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"]),
                    _createVNode(_component_VRow, null, {
                      default: _withCtx(() => [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sourceItems.value, (source) => {
                          return (_openBlock(), _createBlock(_component_VCol, {
                            key: source.id,
                            cols: "12",
                            sm: "6",
                            lg: "4"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_VCard, {
                                rounded: "lg",
                                variant: "outlined",
                                class: "source-card h-100"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VCardText, { class: "d-flex ga-3" }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VCheckboxBtn, {
                                        modelValue: selectedSources.value,
                                        "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((selectedSources).value = $event)),
                                        value: source.id,
                                        color: "primary"
                                      }, null, 8, ["modelValue", "value"]),
                                      _createVNode(_component_VAvatar, {
                                        color: sourceTab.value === 'douban' ? 'green' : 'blue',
                                        variant: "tonal",
                                        rounded: "lg"
                                      }, {
                                        default: _withCtx(() => [
                                          _createVNode(_component_VIcon, {
                                            icon: sourceTab.value === 'douban' ? 'mdi-alpha-d-box' : 'mdi-movie-open-star'
                                          }, null, 8, ["icon"])
                                        ]),
                                        _: 1
                                      }, 8, ["color"]),
                                      _createElementVNode("div", _hoisted_3, [
                                        _createElementVNode("div", _hoisted_4, _toDisplayString(source.name), 1),
                                        _createElementVNode("div", _hoisted_5, _toDisplayString(sourceTab.value === 'douban' ? `豆列 ${source.list_id}` : source.media_type === 'tv' ? '剧集片单' : '电影片单'), 1)
                                      ])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_VCardActions, { class: "px-4 pb-4" }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VSpacer),
                                      _createVNode(_component_VBtn, {
                                        size: "small",
                                        variant: "tonal",
                                        "prepend-icon": "mdi-eye",
                                        loading: actionLoading.value === `preview:${source.id}`,
                                        onClick: $event => (runPreview(source))
                                      }, {
                                        default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                                          _createTextVNode("预览匹配", -1)
                                        ]))]),
                                        _: 1
                                      }, 8, ["loading", "onClick"])
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
                    _cache[26] || (_cache[26] = _createElementVNode("div", { class: "text-h6 mb-1" }, "手动输入公开片单", -1)),
                    _cache[27] || (_cache[27] = _createElementVNode("div", { class: "text-body-2 text-medium-emphasis mb-4" }, "支持 TMDB List 和豆瓣豆列链接。", -1)),
                    _createElementVNode("div", _hoisted_6, [
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
                        default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
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
            _createElementVNode("div", _hoisted_7, [
              _cache[30] || (_cache[30] = _createElementVNode("div", null, [
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
                default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                  _createTextVNode("导出全部", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"]),
              _createVNode(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-import",
                onClick: _cache[6] || (_cache[6] = $event => (importDialog.value = true))
              }, {
                default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
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
                                  _createElementVNode("div", _hoisted_8, _toDisplayString(template.name), 1),
                                  _createElementVNode("div", _hoisted_9, _toDisplayString(template.description || '自定义智能合集模板'), 1),
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
                                    default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
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
                  default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                    _createTextVNode("预览任意片单后，可将结果保存为模板。", -1)
                  ]))]),
                  _: 1
                }))
          ]),
          _: 1
        }),
        _createVNode(_component_VWindowItem, { value: "collections" }, {
          default: _withCtx(() => [
            _cache[36] || (_cache[36] = _createElementVNode("div", { class: "text-h6 mb-1" }, "已同步合集", -1)),
            _cache[37] || (_cache[37] = _createElementVNode("div", { class: "text-body-2 text-medium-emphasis mb-4" }, "重新同步来源，或同时删除管理记录和 Emby 合集。", -1)),
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
                                  _createElementVNode("div", _hoisted_10, [
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
                                    _createElementVNode("div", _hoisted_11, [
                                      _createElementVNode("div", _hoisted_12, _toDisplayString(collection.name), 1),
                                      _createElementVNode("div", _hoisted_13, _toDisplayString(collection.source) + " · 最近同步 " + _toDisplayString(collection.last_sync_at), 1)
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
                                  ])
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VCardActions, null, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VBtn, {
                                    variant: "tonal",
                                    "prepend-icon": "mdi-sync",
                                    loading: actionLoading.value === `resync:${collection.id}`,
                                    onClick: $event => (resyncCollection(collection))
                                  }, {
                                    default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                                      _createTextVNode("重新同步", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["loading", "onClick"]),
                                  _createVNode(_component_VSpacer),
                                  _createVNode(_component_VBtn, {
                                    color: "error",
                                    variant: "text",
                                    "prepend-icon": "mdi-delete-outline",
                                    onClick: $event => (deleteCollection(collection))
                                  }, {
                                    default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
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
                  default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
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
              _createVNode(_component_VCardTitle, { class: "d-flex flex-wrap align-center ga-3 pa-5" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_14, [
                    _createElementVNode("div", _hoisted_15, _toDisplayString(preview.value.title), 1),
                    _createElementVNode("div", _hoisted_16, "共 " + _toDisplayString(preview.value.total_count) + " · 电影 " + _toDisplayString(preview.value.movie_count) + " · 剧集 " + _toDisplayString(preview.value.tv_count) + " · Emby 已有 " + _toDisplayString(preview.value.matched_count) + " · 缺失 " + _toDisplayString(preview.value.missing_count), 1)
                  ]),
                  _createVNode(_component_VTextField, {
                    modelValue: collectionName.value,
                    "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((collectionName).value = $event)),
                    label: "合集名称",
                    density: "compact",
                    "hide-details": "",
                    class: "collection-name"
                  }, null, 8, ["modelValue"]),
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
                    default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                      _createTextVNode("保存为模板", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VDivider),
              _createVNode(_component_VCardText, { class: "pa-4" }, {
                default: _withCtx(() => [
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
                                  _cache[39] || (_cache[39] = _createElementVNode("div", { class: "text-caption" }, "列表总数", -1)),
                                  _createElementVNode("div", _hoisted_17, _toDisplayString(preview.value.total_count), 1)
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
                                  _cache[40] || (_cache[40] = _createElementVNode("div", { class: "text-caption" }, "电影 / 剧集", -1)),
                                  _createElementVNode("div", _hoisted_18, _toDisplayString(preview.value.movie_count) + " / " + _toDisplayString(preview.value.tv_count), 1)
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
                                  _cache[41] || (_cache[41] = _createElementVNode("div", { class: "text-caption" }, "已匹配", -1)),
                                  _createElementVNode("div", _hoisted_19, _toDisplayString(preview.value.matched_count), 1)
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
                                  _cache[42] || (_cache[42] = _createElementVNode("div", { class: "text-caption" }, "缺失", -1)),
                                  _createElementVNode("div", _hoisted_20, _toDisplayString(preview.value.missing_count), 1)
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
                  _createElementVNode("div", _hoisted_21, [
                    _createVNode(_component_VTable, {
                      hover: "",
                      density: "comfortable"
                    }, {
                      default: _withCtx(() => [
                        _cache[43] || (_cache[43] = _createElementVNode("thead", null, [
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
                                      "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((selectedPreviewKeys).value = $event)),
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
                                  class: "poster rounded"
                                }, null, 8, ["src"])
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
                                    }, _toDisplayString(item.title), 9, _hoisted_22))
                                  : (_openBlock(), _createElementBlock("span", _hoisted_23, _toDisplayString(item.title), 1)),
                                _createElementVNode("span", _hoisted_24, _toDisplayString(item.year ? `(${item.year})` : ''), 1),
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  class: "ms-2"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(item.media_type === 'tv' ? '剧集' : '电影'), 1)
                                  ]),
                                  _: 2
                                }, 1024),
                                (!item.matched)
                                  ? (_openBlock(), _createElementBlock("div", _hoisted_25, _toDisplayString(item.missing_reason), 1))
                                  : _createCommentVNode("", true)
                              ]),
                              _createElementVNode("td", null, [
                                _createElementVNode("span", {
                                  class: _normalizeClass(item.matched ? 'text-success' : 'text-medium-emphasis')
                                }, _toDisplayString(item.emby_name || '—'), 3),
                                (item.match_method === 'title')
                                  ? (_openBlock(), _createElementBlock("span", _hoisted_26, "（标题兜底）"))
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
                        key: 0,
                        type: "info",
                        variant: "tonal",
                        class: "mt-3"
                      }, {
                        default: _withCtx(() => [...(_cache[44] || (_cache[44] = [
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
      "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((templateDialog).value = $event)),
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
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((templateName).value = $event)),
                  label: "模板名称"
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextarea, {
                  modelValue: templateDescription.value,
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((templateDescription).value = $event)),
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
                  onClick: _cache[12] || (_cache[12] = $event => (templateDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[45] || (_cache[45] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  loading: actionLoading.value === 'save-template',
                  onClick: saveTemplate
                }, {
                  default: _withCtx(() => [...(_cache[46] || (_cache[46] = [
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
      "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((importDialog).value = $event)),
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
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((importText).value = $event)),
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
                  onClick: _cache[15] || (_cache[15] = $event => (importDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  onClick: importTemplates
                }, {
                  default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
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
    }, 8, ["modelValue"])
  ]))
}
}

};
const SmartCollectionsApp = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-4af477b9"]]);

export { SmartCollectionsApp as S, _export_sfc as _ };
