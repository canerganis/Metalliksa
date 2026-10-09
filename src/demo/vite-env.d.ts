// Minimal typing for the Vite env values the static demo reads (the project does not load vite/client types).
interface ImportMetaEnv {
  readonly VITE_STATIC_DEMO?: string;
  readonly BASE_URL: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
