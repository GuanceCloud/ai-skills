<script setup lang="ts">
import { ref } from 'vue'
const response = ref('尚未请求')
const draft = ref('')
async function loadResource() { const result = await fetch('/sample.json'); response.value = (await result.json()).message }
function triggerError() { setTimeout(() => { throw new Error('acceptance-unhandled-error') }, 0) }
</script>
<template><section><h2>首页</h2><label>本地草稿<input aria-label="本地草稿" v-model="draft"></label><button @click="loadResource">请求资源</button><output>{{ response }}</output><button @click="triggerError">触发错误</button></section></template>
