import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, S as SmartCollectionsApp } from './SmartCollectionsApp-BJCytI4Z.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,withCtx:_withCtx,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');


const {ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: { api: { type: Object, default: () => ({}) } },
  emits: ['close'],
  setup(__props, { emit: __emit }) {


const emit = __emit;
const appRef = ref(null);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");

  return (_openBlock(), _createElementBlock("div", null, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      class: "smart-toolbar"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VIcon, {
          icon: "mdi-playlist-star",
          class: "ms-3 me-2",
          color: "primary"
        }),
        _cache[2] || (_cache[2] = _createElementVNode("div", { class: "text-h6" }, "智能合集", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          icon: "mdi-refresh",
          variant: "text",
          loading: appRef.value?.loading,
          onClick: _cache[0] || (_cache[0] = $event => (appRef.value?.loadStatus()))
        }, null, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createVNode(SmartCollectionsApp, {
      ref_key: "appRef",
      ref: appRef,
      api: __props.api,
      "plugin-id": "SmartCollections",
      "hide-title": ""
    }, null, 8, ["api"])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-cd934720"]]);

export { Page as default };
