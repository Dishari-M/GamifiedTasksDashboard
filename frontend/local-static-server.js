const fs = require("fs");
const http = require("http");
const path = require("path");

const host = process.env.HOST || "127.0.0.1";
const port = Number(process.env.PORT || 3000);
const buildDir = path.join(__dirname, "build");

const types = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
};

const server = http.createServer((req, res) => {
  const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
  const requested = path.normalize(path.join(buildDir, urlPath));
  const isInsideBuild = requested === buildDir || requested.startsWith(buildDir + path.sep);
  const filePath = isInsideBuild && fs.existsSync(requested) && fs.statSync(requested).isFile()
    ? requested
    : path.join(buildDir, "index.html");

  fs.readFile(filePath, (error, content) => {
    if (error) {
      res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      res.end(error.message);
      return;
    }

    res.writeHead(200, {
      "Content-Type": types[path.extname(filePath)] || "application/octet-stream",
      "Cache-Control": "no-store, max-age=0, must-revalidate",
      "Pragma": "no-cache",
      "Expires": "0",
    });
    res.end(content);
  });
});

server.listen(port, host, () => {
  console.log(`Gamified Tasks Dashboard frontend is running at http://${host}:${port}`);
});
