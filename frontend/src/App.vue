<template>
  <!-- Single root: a Fragment root component (multiple top-level nodes) mounted
       at #app crashes Vue's production build with "nextSibling of null". -->
  <div>
    <router-view />
    <ToastHost />
    <TaskHubWidget portal="Accounting" />
  </div>
</template>

<script setup>
import ToastHost from "@/components/shared/ToastHost.vue";
import TaskHubWidget from "@/components/TaskHubWidget.vue";
</script>
