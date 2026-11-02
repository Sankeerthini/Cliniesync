import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api (and /r/<token> shared-report links) to the FastAPI backend (uvicorn on :8000).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000", "/r/": "http://localhost:8000" } },
  build: { outDir: "dist", chunkSizeWarningLimit: 1200 },
});
