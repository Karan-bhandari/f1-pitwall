import { bindings, defineConfig, triggers } from "cf/config";

export default defineConfig(({ mode }) => ({
  worker: {
    name: "f1-pitwall",
    compatibilityDate: "2026-11-24",
    entrypoint: "./worker/index.ts",

    triggers: [
      triggers.fetch({
        pattern: "kbkaran.com/f1-pitwall",
        zone: "kbkaran.com",
      }),
      triggers.fetch({
        pattern: "kbkaran.com/f1-pitwall/*",
        zone: "kbkaran.com",
      }),
      triggers.fetch({
        pattern: "www.kbkaran.com/f1-pitwall",
        zone: "kbkaran.com",
      }),
      triggers.fetch({
        pattern: "www.kbkaran.com/f1-pitwall/*",
        zone: "kbkaran.com",
      }),
    ],

    assets: {
      basePath: "/f1-pitwall",
      notFoundHandling: "single-page-application",
      runWorkerFirst: [
        "/f1-pitwall/api/*",
        "/f1-pitwall/api",
        "/f1-pitwall",
      ],
    },

    env: {
      ASSETS: bindings.assets(),
      BACKEND_ORIGIN: mode !== "development" && bindings.secret(),
      PITWALL_ORIGIN_SECRET: mode !== "development" && bindings.secret(),
    },

    observability: {
      enabled: true,
    },
  },
}));
