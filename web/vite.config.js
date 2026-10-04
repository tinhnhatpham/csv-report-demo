import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Fixed port so it matches ALLOWED_ORIGINS in the backend .env
  server: { port: 5173, strictPort: true },
});
