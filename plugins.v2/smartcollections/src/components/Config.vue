<script setup>
import { onMounted, ref } from 'vue'
import { clone, unwrapResponse } from '../provider'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'SmartCollections' },
})
const emit = defineEmits(['save', 'close'])
const config = ref({})
const embyServers = ref([])

function save() {
  emit('save', clone(config.value))
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
  }
  if (Number(config.value.max_items) === 500) config.value.max_items = 2000
  try {
    const response = await props.api.get(`plugin/${props.pluginId || 'SmartCollections'}/status`)
    const data = unwrapResponse(response) || {}
    embyServers.value = [...new Set([...(data.emby_servers || []), config.value.emby_server].filter(Boolean))]
  } catch (_) {
    embyServers.value = config.value.emby_server ? [config.value.emby_server] : []
  }
})
</script>

<template>
  <div class="pa-4">
    <div class="d-flex align-center mb-4">
      <div>
        <div class="text-h6">智能合集设置</div>
        <div class="text-body-2 text-medium-emphasis">连接 Emby，并控制自动同步行为。</div>
      </div>
      <VSpacer />
      <VBtn color="primary" prepend-icon="mdi-content-save" @click="save">保存</VBtn>
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </div>

    <VCard variant="outlined" rounded="lg">
      <VCardText>
        <VRow>
          <VCol cols="12" md="3"><VSwitch v-model="config.enabled" label="启用定时同步" color="primary" /></VCol>
          <VCol cols="12" md="3"><VSwitch v-model="config.show_sidebar_nav" label="显示侧栏入口" color="primary" /></VCol>
          <VCol cols="12" md="3"><VSwitch v-model="config.onlyonce" label="保存后运行一次" color="primary" /></VCol>
          <VCol cols="12" md="3"><VSwitch v-model="config.notify" label="发送同步通知" color="primary" /></VCol>
          <VCol cols="12" md="3"><VSwitch v-model="config.auto_poster" label="首次同步自动生成海报" color="primary" /></VCol>
          <VCol cols="12" md="4"><VSelect v-model="config.emby_server" :items="embyServers" label="Emby 服务器" hint="选择 MoviePilot 中已启用的 Emby" persistent-hint /></VCol>
          <VCol cols="12" md="4"><VTextField v-model="config.cron" label="Cron 表达式" /></VCol>
          <VCol cols="12" md="4">
            <VSelect v-model="config.sync_mode" label="默认更新模式" :items="[{ title: '完全同步（增删）', value: 'sync' }, { title: '仅追加', value: 'append' }]" />
          </VCol>
          <VCol cols="12" md="6"><VTextField v-model="config.tmdb_token" type="password" label="TMDB v4 Read Access Token" /></VCol>
          <VCol cols="6" md="3"><VTextField v-model="config.language" label="TMDB 语言" /></VCol>
          <VCol cols="6" md="3"><VTextField v-model.number="config.max_items" type="number" label="每个片单最多读取" /></VCol>
          <VCol cols="12" md="4"><VSwitch v-model="config.managed_schedule_enabled" label="定时重同步已管理合集" color="primary" /></VCol>
          <VCol cols="12" md="4"><VTextField v-model="config.managed_schedule_cron" label="已管理合集 Cron" /></VCol>
          <VCol cols="12"><VSwitch v-model="config.use_proxy" label="访问公开片单时使用 MoviePilot 代理" color="primary" /></VCol>
        </VRow>
      </VCardText>
    </VCard>
  </div>
</template>
