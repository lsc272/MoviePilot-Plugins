<script setup>
import SmartCollectionsApp from './SmartCollectionsApp.vue'
defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'SmartCollections' },
})
</script>

<template>
  <SmartCollectionsApp :api="api" :plugin-id="pluginId" />
</template>
