<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
<template><section><h2>详情页</h2><p>当前页码：{{ route.query.page }}</p><img src="/mark.svg" alt="资源图标" width="48" height="48"></section></template>
