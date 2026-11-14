import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The live server (CC-L) listens on :8000. With none running the app plays the bundle as it is.
const proxy = { "/api": { target: "http://localhost:8000", changeOrigin: false } };

export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
  build: {
    chunkSizeWarningLimit: 2500,
  },
});
