// Servidor do simulador "Cheia do Pardinho" (Programa MUDA / UNISC)
// - entrega os arquivos de ./public
// - repassa as consultas para a API da Defesa Civil RS (evita o bloqueio de CORS no navegador)
// Sem dependencias: precisa so de Node 18 ou mais novo.
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = process.env.PORT || 3000;
const API = "https://redehidrometeorologica.defesacivil.rs.gov.br/graphql";
const PUB = path.join(__dirname, "public");
const TIPOS = { ".html": "text/html; charset=utf-8", ".png": "image/png", ".json": "application/json; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".ico": "image/x-icon" };

// cache simples: a API so muda a cada 5 min e limita 120 consultas/min por IP do servidor
const cache = new Map();
const TTL_TAGS = 60 * 1000, TTL_HIST = 5 * 60 * 1000;

async function repassar(corpo) {
  const tipo = /query\s+Tags_data/.test(corpo) ? "tags" : /query\s+Historic/.test(corpo) ? "hist" : null;
  if (!tipo) return { status: 400, body: JSON.stringify({ errors: [{ message: "Consulta não permitida." }] }) };
  const chave = tipo === "tags" ? "tags" : corpo;
  const c = cache.get(chave);
  if (c && Date.now() - c.t < (tipo === "tags" ? TTL_TAGS : TTL_HIST)) return { status: 200, body: c.body };
  const r = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json" }, body: corpo, signal: AbortSignal.timeout(20000) });
  const body = await r.text();
  if (r.ok) {
    cache.set(chave, { t: Date.now(), body });
    if (cache.size > 200) cache.delete(cache.keys().next().value);
  }
  return { status: r.status, body };
}

http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://x");
    if (url.pathname === "/api/defesacivil") {
      if (req.method !== "POST") { res.writeHead(405); return res.end(); }
      let corpo = "";
      for await (const pedaco of req) { corpo += pedaco; if (corpo.length > 20000) { res.writeHead(413); return res.end(); } }
      const r = await repassar(corpo);
      res.writeHead(r.status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
      return res.end(r.body);
    }
    if (url.pathname === "/saude") { res.writeHead(200); return res.end("ok"); }
    let arq = path.normalize(decodeURIComponent(url.pathname)).replace(/^([/\\])+/, "");
    if (!arq) arq = "index.html";
    const cam = path.join(PUB, arq);
    if (!cam.startsWith(PUB)) { res.writeHead(403); return res.end(); }
    fs.readFile(cam, (err, dados) => {
      if (err) { res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" }); return res.end("Não encontrado"); }
      const ext = path.extname(cam);
      res.writeHead(200, { "Content-Type": TIPOS[ext] || "application/octet-stream", "Cache-Control": ext === ".html" ? "no-cache" : "public, max-age=86400" });
      res.end(dados);
    });
  } catch (e) {
    res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ errors: [{ message: "Falha ao consultar a Defesa Civil: " + e.message }] }));
  }
}).listen(PORT, () => console.log(`Cheia do Pardinho rodando na porta ${PORT}`));
