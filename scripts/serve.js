// 零依赖静态文件服务：本地预览 site/index.html
// 用法：node scripts/serve.js [端口]  然后访问 http://localhost:8000/site/
const http = require("http");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const port = Number(process.argv[2]) || Number(process.env.PORT) || 8000;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

http
  .createServer((req, res) => {
    const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
    let file = path.normalize(path.join(root, urlPath));

    // 防目录穿越
    if (!file.startsWith(root)) {
      res.writeHead(403).end("Forbidden");
      return;
    }

    fs.stat(file, (err, st) => {
      if (!err && st.isDirectory()) file = path.join(file, "index.html");
      fs.readFile(file, (err2, data) => {
        if (err2) {
          res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
          res.end("404 Not Found: " + urlPath);
          return;
        }
        res.writeHead(200, {
          "Content-Type": MIME[path.extname(file).toLowerCase()] || "application/octet-stream",
          "Cache-Control": "no-store",
        });
        res.end(data);
      });
    });
  })
  .listen(port, () => {
    console.log(`Serving ${root}`);
    console.log(`Open: http://localhost:${port}/site/`);
  });
