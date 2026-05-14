import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const maxxiApiUrl = (env.VITE_MAXXI_API_URL || "https://mxcdn.vercel.app").replace(/\/+$/, "");

  return {
    server: {
      host: "::",
      hmr: {
        overlay: false,
      },
      proxy: {
        "/api": {
          target: maxxiApiUrl,
          changeOrigin: true,
          secure: true,
        },
      },
    },
    plugins: [react()].filter(Boolean),
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
      dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime", "@tanstack/react-query"],
    },
  };
});
