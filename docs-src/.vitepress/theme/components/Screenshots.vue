<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { withBase } from "vitepress";

interface Shot {
  src: string;
  alt: string;
  eyebrow: string;
  title: string;
  paragraphs: string[];
}

const shots: Shot[] = [
  {
    src: "/assets/screenshots/dashboard.png",
    alt: "Atrium dashboard showing active portals, guest counts, and recent portal activity",
    eyebrow: "Dashboard",
    title: "One overview, every site",
    paragraphs: [
      "Active portals, live guest counts, and recent activity across every tenant - at a glance, the moment you log in.",
    ],
  },
  {
    src: "/assets/screenshots/tenants.png",
    alt: "Tenants page showing multiple client organisations managed under one Atrium install",
    eyebrow: "Multi-tenant",
    title: "Built for managing other people's networks",
    paragraphs: [
      "Running guest WiFi for multiple clients as an MSP? Each one is a fully isolated tenant - their own sites, portals, and users, all under a single install you maintain.",
    ],
  },
  {
    src: "/assets/screenshots/sites.png",
    alt: "Sites page showing multiple UniFi sites across different tenants, each assignable and each with their own portals",
    eyebrow: "Multi-site",
    title: "One client, many locations, many SSIDs",
    paragraphs: [
      "A tenant isn't limited to one site - assign as many UniFi sites to them as they have locations, each with its own portal, branding, and guest data.",
      "<strong>Down to the SSID:</strong> a single site can run a different portal per SSID - staff WiFi, guest WiFi, and a lobby kiosk network can each show something completely different. UniFi's built-in guest portal can't do that.",
    ],
  },
  {
    src: "/assets/screenshots/controllers.png",
    alt: "Controllers page showing a connected UniFi controller, its auth mode, owner, and sync schedule",
    eyebrow: "UniFi controllers",
    title: "Connect once, sync automatically",
    paragraphs: [
      "Add a self-hosted UniFi controller or UniFi Site Manager (cloud), with password or 2FA-safe API key auth. Sites and access points sync on a schedule you set - hourly, daily, or on demand.",
    ],
  },
  {
    src: "/assets/screenshots/portal_editor.png",
    alt: "Portal appearance editor showing primary, secondary, heading, body, and button text colors, font, layout, and logo/background/favicon upload",
    eyebrow: "Portal builder",
    title: "Brand every portal to match",
    paragraphs: [
      "Colors down to heading, body, and button text, fonts, layout, logo, background, and favicon - tailor the guest login experience per portal, per tenant, without touching code.",
      "Ask guests whatever you need on the way in: free-form fields, or specific types like email and phone. Every answer is captured against the session, ready to filter and export from analytics.",
    ],
  },
  {
    src: "/assets/screenshots/analytics.png",
    alt: "Guest analytics page showing total sessions, unique devices, return visitor rate, and a sessions-over-time chart",
    eyebrow: "Analytics",
    title: "Know who's actually connecting",
    paragraphs: [
      "Total sessions, unique devices, return-visitor rate, and auth failures per portal, with sessions charted over time and by peak hour and day of week. Filter by device, SSID, or date range, and export to CSV.",
    ],
  },
  {
    src: "/assets/screenshots/portals.png",
    alt: "Portals list page showing configured portals, their site, auth type, and status",
    eyebrow: "Portals",
    title: "All your portals, one list",
    paragraphs: [
      "Search and manage every captive portal instance across every site, with direct links to guests, analytics, and vouchers.",
    ],
  },
  {
    src: "/assets/screenshots/settings_dark.png",
    alt: "Settings page in dark mode showing timezone, date format, and routing configuration",
    eyebrow: "Settings",
    title: "Configured your way",
    paragraphs: [
      "Timezone, date format, routing, guest defaults, security, and email - plus a dark theme that's genuinely easy on the eyes.",
    ],
  },
];

const openSrc = ref<string | null>(null);
const openAlt = ref("");

function open(shot: Shot) {
  openSrc.value = shot.src;
  openAlt.value = shot.alt;
}
function close() {
  openSrc.value = null;
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") close();
}
onMounted(() => window.addEventListener("keydown", onKeydown));
onUnmounted(() => window.removeEventListener("keydown", onKeydown));
</script>

<template>
  <div class="atrium-shots">
    <div v-for="(shot, i) in shots" :key="shot.src" class="atrium-shot" :class="{ reverse: i % 2 === 1 }">
      <div class="atrium-shot-frame">
        <img
          :src="withBase(shot.src)"
          :alt="shot.alt"
          tabindex="0"
          role="button"
          @click="open(shot)"
          @keydown.enter.prevent="open(shot)"
          @keydown.space.prevent="open(shot)"
        />
      </div>
      <div class="atrium-shot-text">
        <span class="atrium-eyebrow">{{ shot.eyebrow }}</span>
        <h3>{{ shot.title }}</h3>
        <p v-for="(para, j) in shot.paragraphs" :key="j" v-html="para"></p>
      </div>
    </div>
  </div>

  <div class="atrium-lightbox" :class="{ open: openSrc }" @click="close">
    <button class="atrium-lightbox-close" aria-label="Close" @click.stop="close">&times;</button>
    <img v-if="openSrc" :src="withBase(openSrc)" :alt="openAlt" @click.stop />
  </div>
</template>
