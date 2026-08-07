import { defineConfig } from "vitepress";

export default defineConfig({
  title: "Atrium",
  description:
    "Atrium is a self-hosted admin panel for running branded guest WiFi captive portals across multiple tenants and sites on a UniFi network.",
  base: "/Atrium/",
  outDir: "../docs",
  lastUpdated: true,

  head: [
    ["link", { rel: "icon", href: "/Atrium/assets/favicon.ico" }],
    ["link", { rel: "apple-touch-icon", href: "/Atrium/assets/icon-512.png" }],
    ["meta", { property: "og:title", content: "Atrium - Multi-tenant captive portal management" }],
    [
      "meta",
      {
        property: "og:description",
        content:
          "Self-hosted admin panel for running branded guest WiFi captive portals across multiple tenants and sites on a UniFi network.",
      },
    ],
    ["meta", { property: "og:image", content: "https://agent-squirrel.github.io/Atrium/assets/social-preview.png" }],
    ["meta", { property: "og:url", content: "https://agent-squirrel.github.io/Atrium/" }],
    ["meta", { name: "twitter:card", content: "summary_large_image" }],
  ],

  themeConfig: {
    logo: "/assets/icon-mark.svg",

    nav: [
      { text: "Home", link: "/" },
      { text: "Install", link: "/install" },
      { text: "Guide", link: "/guide/" },
    ],

    sidebar: {
      "/guide/": [
        {
          text: "Guide",
          items: [
            { text: "Introduction", link: "/guide/" },
            { text: "Getting Started", link: "/guide/getting-started" },
            { text: "Configure UniFi", link: "/guide/configure-unifi" },
            { text: "Set up Google Sign-In", link: "/guide/google-sign-in" },
          ],
        },
      ],
    },

    socialLinks: [{ icon: "github", link: "https://github.com/agent-squirrel/Atrium" }],

    search: {
      provider: "local",
    },
  },
});
