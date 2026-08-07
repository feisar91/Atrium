<script setup lang="ts">
import { withBase } from "vitepress";
</script>

<template>
  <div class="atrium-cta">
    <span class="atrium-eyebrow">Self-hosted</span>
    <h2>Run it on your own infrastructure</h2>
    <p>Docker Compose, published images, five minutes. Your data stays on your server.</p>
    <a class="VPButton medium brand" :href="withBase('/install')">Read the install guide →</a>
  </div>
</template>
