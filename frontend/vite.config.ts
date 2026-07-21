import fs from "node:fs"
import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

const RAW_IMAGES = path.resolve(__dirname, "../backend/data/raw-images")

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "raw-images",
      configureServer(server) {
        server.middlewares.use("/v1/media", (req, res, next) => {
          const mediaId = (req.url ?? "").replace(/^\//, "").split("?")[0]
          if (!mediaId || mediaId.includes("/") || mediaId.includes("..")) return next()
          const file = path.join(RAW_IMAGES, `${mediaId}.png`)
          if (!fs.existsSync(file)) return next()
          res.setHeader("Content-Type", "image/png")
          res.setHeader("Cache-Control", "public, max-age=31536000, immutable")
          fs.createReadStream(file).pipe(res)
        })
      },
    },
  ],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
})
