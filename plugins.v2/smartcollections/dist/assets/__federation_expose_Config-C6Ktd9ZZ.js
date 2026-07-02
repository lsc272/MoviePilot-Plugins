import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { c as clone, u as unwrapResponse } from './provider-DU2BtLoi.js';

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "pa-4" };
const _hoisted_2 = { class: "d-flex align-center mb-4" };

const {onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'SmartCollections' },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const config = ref({});
const embyServers = ref([]);

function save() {
  emit('save', clone(config.value));
}

onMounted(async () => {
  config.value = {
    enabled: false,
    show_sidebar_nav: true,
    auto_poster: true,
    onlyonce: false,
    notify: false,
    use_proxy: false,
    cron: '0 4 * * *',
    emby_server: '',
    sync_mode: 'sync',
    tmdb_token: '',
    language: 'zh-CN',
    max_items: 2000,
    managed_schedule_enabled: false,
    managed_schedule_cron: '0 4 * * *',
    ...(clone(props.initialConfig) || {}),
  };
  if (Number(config.value.max_items) === 500) config.value.max_items = 2000;
  try {
    const response = await props.api.get(`plugin/${props.pluginId || 'SmartCollections'}/status`);
    const data = unwrapResponse(response) || {};
    embyServers.value = [...new Set([...(data.emby_servers || []), config.value.emby_server].filter(Boolean))];
  } catch (_) {
    embyServers.value = config.value.emby_server ? [config.value.emby_server] : [];
  }
});

return (_ctx, _cache) => {
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("div", _hoisted_2, [
      _cache[16] || (_cache[16] = _createElementVNode("div", null, [
        _createElementVNode("div", { class: "text-h6" }, "智能合集设置"),
        _createElementVNode("div", { class: "text-body-2 text-medium-emphasis" }, "连接 Emby，并控制自动同步行为。")
      ], -1)),
      _createVNode(_component_VSpacer),
      _createVNode(_component_VBtn, {
        color: "primary",
        "prepend-icon": "mdi-content-save",
        onClick: save
      }, {
        default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
          _createTextVNode("保存", -1)
        ]))]),
        _: 1
      }),
      _createVNode(_component_VBtn, {
        icon: "mdi-close",
        variant: "text",
        onClick: _cache[0] || (_cache[0] = $event => (emit('close')))
      })
    ]),
    _createVNode(_component_VCard, {
      variant: "outlined",
      rounded: "lg"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardText, null, {
          default: _withCtx(() => [
            _createVNode(_component_VRow, null, {
              default: _withCtx(() => [
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "3"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      modelValue: config.value.enabled,
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((config.value.enabled) = $event)),
                      label: "启用定时同步",
                      color: "primary"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "3"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      modelValue: config.value.show_sidebar_nav,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((config.value.show_sidebar_nav) = $event)),
                      label: "显示侧栏入口",
                      color: "primary"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "3"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      modelValue: config.value.onlyonce,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((config.value.onlyonce) = $event)),
                      label: "保存后运行一次",
                      color: "primary"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "3"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      modelValue: config.value.notify,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((config.value.notify) = $event)),
                      label: "发送同步通知",
                      color: "primary"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "3"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      modelValue: config.value.auto_poster,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((config.value.auto_poster) = $event)),
                      label: "首次同步自动生成海报",
                      color: "primary"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSelect, {
                      modelValue: config.value.emby_server,
                      "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((config.value.emby_server) = $event)),
                      items: embyServers.value,
                      label: "Emby 服务器",
                      hint: "选择 MoviePilot 中已启用的 Emby",
                      "persistent-hint": ""
                    }, null, 8, ["modelValue", "items"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: config.value.cron,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((config.value.cron) = $event)),
                      label: "Cron 表达式"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSelect, {
                      modelValue: config.value.sync_mode,
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((config.value.sync_mode) = $event)),
                      label: "默认更新模式",
                      items: [{ title: '完全同步（增删）', value: 'sync' }, { title: '仅追加', value: 'append' }]
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: config.value.tmdb_token,
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((config.value.tmdb_token) = $event)),
                      type: "password",
                      label: "TMDB v4 Read Access Token"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "6",
                  md: "3"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: config.value.language,
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((config.value.language) = $event)),
                      label: "TMDB 语言"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "6",
                  md: "3"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: config.value.max_items,
                      "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((config.value.max_items) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      label: "每个片单最多读取"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      modelValue: config.value.managed_schedule_enabled,
                      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((config.value.managed_schedule_enabled) = $event)),
                      label: "定时重同步已管理合集",
                      color: "primary"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  md: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: config.value.managed_schedule_cron,
                      "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((config.value.managed_schedule_cron) = $event)),
                      label: "已管理合集 Cron"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, { cols: "12" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      modelValue: config.value.use_proxy,
                      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((config.value.use_proxy) = $event)),
                      label: "访问公开片单时使用 MoviePilot 代理",
                      color: "primary"
                    }, null, 8, ["modelValue"])
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
    })
  ]))
}
}

};

export { _sfc_main as default };
