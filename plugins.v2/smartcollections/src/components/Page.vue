<script setup>
import { ref } from 'vue'
import SmartCollectionsApp from './SmartCollectionsApp.vue'

defineProps({ api: { type: Object, default: () => ({}) } })
const emit = defineEmits(['close'])
const appRef = ref(null)
</script>

<template>
  <div>
    <VToolbar density="comfortable" class="smart-toolbar">
      <VIcon icon="mdi-playlist-star" class="ms-3 me-2" color="primary" />
      <div class="text-h6">智能合集</div>
      <VSpacer />
      <VBtn icon="mdi-refresh" variant="text" :loading="appRef?.loading" @click="appRef?.loadStatus()" />
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />
    <SmartCollectionsApp ref="appRef" :api="api" plugin-id="SmartCollections" hide-title />
  </div>
</template>

<style scoped>
.smart-toolbar { position: sticky; top: 0; z-index: 10; background: rgb(var(--v-theme-surface)); }
</style>
