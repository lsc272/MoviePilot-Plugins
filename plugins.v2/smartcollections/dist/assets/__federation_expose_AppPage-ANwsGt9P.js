import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { S as SmartCollectionsApp } from './SmartCollectionsApp-CL4DjLAV.js';

const {openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');

const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'SmartCollections' },
},
  setup(__props) {



return (_ctx, _cache) => {
  return (_openBlock(), _createBlock(SmartCollectionsApp, {
    api: __props.api,
    "plugin-id": __props.pluginId
  }, null, 8, ["api", "plugin-id"]))
}
}

};

export { _sfc_main as default };
