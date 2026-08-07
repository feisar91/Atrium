import DefaultTheme from "vitepress/theme";
import type { Theme } from "vitepress";
import Screenshots from "./components/Screenshots.vue";
import SelfHostedCta from "./components/SelfHostedCta.vue";
import "./custom.css";

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component("Screenshots", Screenshots);
    app.component("SelfHostedCta", SelfHostedCta);
  },
} satisfies Theme;
