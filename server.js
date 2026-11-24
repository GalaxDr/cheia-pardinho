// Servidor do simulador "Cheia do Pardinho" (Programa MUDA / UNISC)
// - entrega os arquivos de ./public
// - repassa as consultas para a API da Defesa Civil RS (evita o bloqueio de CORS no navegador)
// - junta os pluviometros UNISC e CEMADEN da regiao em /api/pluviometros
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

// ---------- Pluviometros UNISC e CEMADEN (mesmas fontes do projeto pluvio-audit) ----------
// Endpoints nao documentados: podem mudar sem aviso. Tudo em cache para nao sobrecarregar as fontes.
const UNISC = "https://estacaobackend.unisc.br";
const CEM_LISTA = "https://resources.cemaden.gov.br/graficos/interativo/getJson2.php?uf=RS";
const CEM_HORARIO = "https://mapservices.cemaden.gov.br/MapaInterativoWS/resources/horario";
// caixa em volta da sub-bacia (a pagina recorta pelo contorno exato do mapa)
const CAIXA = { latMin: -30.0, latMax: -29.0, lonMin: -53.0, lonMax: -52.0 };
const MUNICIPIOS = ["SINIMBU", "SANTA CRUZ DO SUL", "VALE DO SOL", "HERVEIRAS", "GRAMADO XAVIER", "BOQUEIRAO DO LEAO", "VERA CRUZ",
  "SOBRADINHO", "BARROS CASSAL", "PASSO DO SOBRADO", "VENANCIO AIRES", "RIO PARDO", "CANDELARIA", "LAGOA BONITA DO SUL", "ARROIO DO TIGRE"];
const TTL_PLUV = 5 * 60 * 1000, TTL_COORD = 24 * 3600 * 1000;
let pluvCache = null, pluvEmAndamento = null;
const coordCem = new Map();
const semAcento = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase().trim();
const naCaixa = (lat, lon) => lat >= CAIXA.latMin && lat <= CAIXA.latMax && lon >= CAIXA.lonMin && lon <= CAIXA.lonMax;
function paraMm(v) {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const a = String(v).match(/-?\d[\d.,]*/); if (!a) return null;
  let n = a[0].replace(/[.,]+$/, "");
  if (n.includes(",") && n.includes(".")) n = n.replace(/\./g, "").replace(",", "."); else if (n.includes(",")) n = n.replace(",", ".");
  const x = Number(n); return Number.isFinite(x) ? x : null;
}
async function json(url, ms = 20000) {
  const r = await fetch(url, { signal: AbortSignal.timeout(ms), headers: { "User-Agent": "cheia-pardinho/web" } });
  if (!r.ok) throw new Error(`HTTP ${r.status} em ${new URL(url).host}`);
  return r.json();
}
async function emLotes(itens, lim, fn) {
  const out = new Array(itens.length); let i = 0;
  await Promise.all(Array.from({ length: Math.min(lim, itens.length) }, async () => { while (i < itens.length) { const k = i++; out[k] = await fn(itens[k]); } }));
  return out;
}
// serie horaria do Mapa Interativo: matriz data x hora, rotulos em UTC; null = hora sem dado
function serieHoraria(d) {
  const { horarios, datas, acumulados } = d;
  if (!Array.isArray(horarios) || !Array.isArray(datas) || !Array.isArray(acumulados) || !datas.length) return [];
  const [d0, m0, a0] = datas[0].split("/").map(Number);
  let dia = Date.UTC(a0, m0 - 1, d0), hAnt = null;
  const chave = (t) => { const x = new Date(t); return `${String(x.getUTCDate()).padStart(2, "0")}/${String(x.getUTCMonth() + 1).padStart(2, "0")}/${x.getUTCFullYear()}`; };
  const linha = new Map(datas.map((s, i) => [s, i]));
  return horarios.map((rot, i) => {
    const h = parseInt(String(rot), 10);
    if (hAnt !== null && h === 0) dia += 24 * 3600 * 1000;
    hAnt = h;
    const l = linha.get(chave(dia));
    return { t: dia + h * 3600 * 1000, v: l === undefined ? null : paraMm((acumulados[l] || [])[i]) };
  });
}
async function lerUnisc() {
  const lista = await json(`${UNISC}/estacao-meteorologica`);
  const sel = lista.map((e) => ({ cod: e.cod_estacao_meteorologica, nome: String(e.nome || "").trim(), lat: Number(e.latitude), lon: Number(e.longitude), ativa: e.status !== false }))
    .filter((e) => Number.isFinite(e.lat) && Number.isFinite(e.lon) && naCaixa(e.lat, e.lon));
  return emLotes(sel, 4, async (e) => {
    try {
      const d = await json(`${UNISC}/gerenciamento-estacao-meteorologica/resumoUltimaLeitura/codEstacao/${e.cod}`, 15000);
      const x = d.dados_especificos_elysios_resumo_leitura || {};
      let ts = d.dth_leitura ? String(d.dth_leitura) : null; if (ts && !/[zZ]|[+-]\d\d:?\d\d$/.test(ts)) ts += "Z";
      return { ...e, ts: ts ? Date.parse(ts) || null : null, dia: paraMm(x.pluviosidade_acumulada_dia), h24: paraMm(x.pluviosidade_acumulada_ultimas_24_horas), d7: paraMm(x.pluviosidade_acumulada_ultimos_7_dias) };
    } catch (err) { return { ...e, erro: err.message }; }
  });
}
async function lerCemaden() {
  const lista = await json(CEM_LISTA, 30000);
  const daRegiao = lista.filter((x) => x.tipoestacao === 1 && MUNICIPIOS.includes(semAcento(x.cidade)));
  const r = await emLotes(daRegiao, 4, async (x) => {
    try {
      const d = await json(`${CEM_HORARIO}/${x.idestacao}/24`, 30000);
      const lat = d.estacao?.latitude, lon = d.estacao?.longitude;
      if (typeof lat !== "number" || typeof lon !== "number") return null;
      coordCem.set(x.idestacao, { lat, lon, t: Date.now() });
      if (!naCaixa(lat, lon)) return null;
      const s = serieHoraria(d), val = s.filter((p) => p.v !== null);
      const ult = val[val.length - 1];
      return { id: x.idestacao, nome: d.estacao?.nome || x.nomeestacao, cidade: x.cidade, lat, lon,
        h24: val.length ? Math.round(val.reduce((a, p) => a + p.v, 0) * 10) / 10 : null, horas: val.length,
        h1: ult ? ult.v : null, ts: ult ? ult.t : null };
    } catch (err) {
      const c = coordCem.get(x.idestacao);
      return c && naCaixa(c.lat, c.lon) ? { id: x.idestacao, nome: x.nomeestacao, cidade: x.cidade, lat: c.lat, lon: c.lon, h24: null, erro: err.message } : null;
    }
  });
  return r.filter(Boolean);
}
async function pluviometros() {
  if (pluvCache && Date.now() - pluvCache.t < TTL_PLUV) return pluvCache.body;
  if (!pluvEmAndamento) pluvEmAndamento = (async () => {
    const [u, c] = await Promise.allSettled([lerUnisc(), lerCemaden()]);
    const body = JSON.stringify({
      ts: Date.now(),
      unisc: u.status === "fulfilled" ? u.value : [], cemaden: c.status === "fulfilled" ? c.value : [],
      erros: [u.status === "rejected" ? "UNISC: " + u.reason.message : null, c.status === "rejected" ? "CEMADEN: " + c.reason.message : null].filter(Boolean)
    });
    pluvCache = { t: Date.now(), body };
    return body;
  })().finally(() => { pluvEmAndamento = null; });
  return pluvEmAndamento;
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
    if (url.pathname === "/api/pluviometros") {
      const body = await pluviometros();
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
      return res.end(body);
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
