/* Situação dos açudes com boletim de acompanhamento da alocação de água (ANA).
   Lê só dados/painel.json (gerado por coletor/atualiza.py). Um filtro único (UF e busca) vale para o mapa e para as
   duas visualizações dos açudes: por sistema hídrico (cartões) ou em tabela. Formatação e componentes seguem o
   protótipo do novo SAR (js/base.js e js/exportacao.js de dlpena/prototipo-sar-design). */
"use strict";

const COR = {};
// "sem_informacao" não vira etiqueta: o cartão mostra "Sem informação" no lugar do valor
const ALERTAS = {
  medicao_antiga: (r, pag) => `Sem medição nos últimos ${janela(pag)} dias`,
  data_futura: () => "Data de medição a confirmar",
  volume_fora_da_faixa: () => "Valor a confirmar"
};
const janela = pag => pag.P.criterio.janela_medicao_dias || 30;
// até onde a última medição é buscada (sem nada nesse prazo, o açude fica "sem informação")
const prazoBusca = pag => {
  const d = Math.max(pag.P.criterio.busca_medicao_dias || 0, janela(pag));
  return d >= 365 && d % 365 === 0 ? `${d / 365} ano${d > 365 ? "s" : ""}` : `${d} dias`;
};
const SECOES = [
  ["mapa", "Mapa"],
  ["acudes", "Açudes"],
  ["sobre", "Sobre os dados"]
];
const ICONE = {
  sistemas: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1"/><rect x="9" y="1.5" width="5.5" height="5.5" rx="1"/><rect x="1.5" y="9" width="5.5" height="5.5" rx="1"/><rect x="9" y="9" width="5.5" height="5.5" rx="1"/></svg>',
  tabela: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3h13M1.5 6.5h13M1.5 10h13M1.5 13.5h13"/></svg>'
};
const VISTAS = [
  ["sistemas", "Por sistema hídrico", "Cada sistema traz o boletim mais recente e o acesso aos termos e boletins anteriores."],
  ["tabela", "Tabela", "Todos os açudes numa lista, ordenada por UF. Para usar em planilha, baixe o CSV."]
];

/* ---------- utilitários (os do protótipo: fmt, dBR) ---------- */
const fmt = (v, n = 1) =>
  v == null || isNaN(v)
    ? "–"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: n, maximumFractionDigits: n });
const dBR = iso => iso.slice(8, 10) + "/" + iso.slice(5, 7) + "/" + iso.slice(0, 4);
const hBR = iso => dBR(iso) + ", " + iso.slice(11, 16);
const mesCurto = mes => ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"][+mes.slice(5, 7) - 1] + "/" + mes.slice(0, 4);
const esc = s =>
  String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
// busca sem acento nem pontuação: "mae dagua" acha "Mãe d'Água"
const semAcento = s =>
  s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9 ]+/g, "").replace(/\s+/g, " ");
function diasDesde(iso) {
  const h = new Date();
  const d = new Date(iso + "T12:00:00");
  return Math.round((Date.UTC(h.getFullYear(), h.getMonth(), h.getDate()) - Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())) / 864e5);
}
const lembrar = (k, v) => {
  try {
    localStorage.setItem("alocacao." + k, v);
  } catch (e) {
    /* sem armazenamento: só não lembra */
  }
};
const lembrado = k => {
  try {
    return localStorage.getItem("alocacao." + k);
  } catch (e) {
    return null;
  }
};

/* ---------- partida ---------- */
async function iniciar() {
  COR.ana = getComputedStyle(document.documentElement).getPropertyValue("--ana").trim();
  let P;
  try {
    const r = await fetch("dados/painel.json", { cache: "no-cache" });
    P = await r.json();
  } catch (e) {
    document.getElementById("carimbo").innerHTML = "<span>Não foi possível carregar os dados. Tente recarregar a página.</span>";
    return;
  }
  const vista = lembrado("vista");
  const pag = {
    P,
    sis: Object.fromEntries(P.sistemas.map(s => [s.id, s])),
    uf: "",
    busca: "",
    vista: VISTAS.some(([v]) => v === vista) ? vista : "sistemas"
  };
  carimbo(pag);
  esqueleto(pag);
  indices();
  filtros(pag);
  mapa(pag);
  vistas(pag);
  sobre(pag);
  aplicar(pag);
}

function carimbo(pag) {
  const { P } = pag;
  document.getElementById("carimbo").innerHTML =
    `<span>Atualizado em <b>${hBR(P.fontes.medicao.lido_em)}</b></span>` +
    `<span><b>${P.reservatorios.length}</b> açudes em <b>${P.sistemas.length}</b> sistemas hídricos</span>` +
    `<span>Boletim mais recente: <b>${esc(P.criterio.rotulo)}</b></span>`;
}

function esqueleto(pag) {
  const sec = (id, n, titulo, sub, corpo, baixar = "") =>
    `<section class="cartao secao" id="${id}">${baixar}<h2><small>${n}</small>${titulo}</h2>${sub ? `<p class="sub">${sub}</p>` : ""}${corpo}</section>`;
  const btn = (id, rot) =>
    `<div class="baixar"><button type="button" id="${id}"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8M4.5 6.5 8 10l3.5-3.5M3 13h10" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>${rot}</button></div>`;
  document.getElementById("conteudo").innerHTML =
    `<nav class="indice" aria-label="Seções da página">${SECOES.map(([id, t]) => `<a href="#${id}">${t}</a>`).join("")}</nav>` +
    `<div class="intro"><p>A alocação de água é um processo de gestão empregado para disciplinar os usos múltiplos da ` +
    `água em sistemas hídricos com conflito pelo uso, situação emergencial ou estiagem intensa. As decisões, tomadas em ` +
    `reuniões com órgãos gestores, operadores de reservatórios e usuários, são registradas no Termo de Alocação de Água ` +
    `e acompanhadas em boletins mensais. Esta página reúne os açudes desses sistemas, com a última medição de cada um e ` +
    `o boletim mais recente.</p></div>` +
    `<div id="antes-filtros" aria-hidden="true"></div><div class="filtros" role="search" aria-label="Filtrar açudes"><div class="presets" id="presets-uf" role="group" aria-label="Filtrar por UF"></div>` +
    `<input type="search" id="busca" placeholder="Buscar açude ou sistema" aria-label="Buscar açude ou sistema">` +
    `<span class="contagem" id="contagem" aria-live="polite"></span></div>` +
    sec("mapa", 1, "Mapa", "Cada triângulo é um açude. <span class=\"dica\">Clique ou toque para ver os dados dele.</span>",
      `<div id="mapa-acudes" role="region" aria-label="Mapa dos açudes"></div>`, btn("baixar-kmz", "KMZ")) +
    sec("acudes", 2, "Açudes", "",
      `<div class="abas" id="vistas" role="tablist" aria-label="Visualização dos açudes"></div>` +
      `<p class="dica-aba" id="dica-aba"></p><div id="lista-acudes" role="tabpanel"></div>`,
      btn("baixar-csv", "CSV")) +
    sec("sobre", 3, "Sobre os dados", "Origem e significado dos números.", `<div class="fontes" id="sobre-corpo"></div>`);
}

/* índice: chips no celular (nav.indice) e lista na barra lateral no desktop, como no protótipo */
function indices() {
  const lat = document.querySelector(".lateral-indice");
  lat.innerHTML =
    `<span class="rot">Nesta página</span>` + SECOES.map(([id, t], i) => `<a href="#${id}"><i>${i + 1}</i>${t}</a>`).join("");
  lat.hidden = false;
  const links = [...lat.querySelectorAll("a")];
  const obs = new IntersectionObserver(
    ent => ent.forEach(e => e.isIntersecting && links.forEach(a => a.classList.toggle("ativo", a.hash === "#" + e.target.id))),
    { rootMargin: "-20% 0px -70% 0px" }
  );
  SECOES.forEach(([id]) => obs.observe(document.getElementById(id)));
}

/* ---------- filtro único: UF e busca valem para o mapa e para as duas visualizações ---------- */
function filtros(pag) {
  const ufs = [...new Set(pag.P.reservatorios.map(r => r.uf))].sort();
  const pres = document.getElementById("presets-uf");
  pres.innerHTML = [["", "Todas as UFs"], ...ufs.map(u => [u, u])]
    .map(([v, t]) => `<button type="button" class="preset${v === "" ? " ativo" : ""}" data-uf="${v}" aria-pressed="${v === ""}">${t}</button>`)
    .join("");
  pres.addEventListener("click", ev => {
    const b = ev.target.closest("button");
    if (!b) return;
    pag.uf = b.dataset.uf;
    aplicar(pag);
  });
  const busca = document.getElementById("busca");
  busca.addEventListener("input", () => {
    pag.busca = semAcento(busca.value.trim());
    aplicar(pag);
  });
  barraPresa();
}
/* barra de filtros presa no topo: marca quando está presa (linha embaixo) e desconta a altura dela da rolagem por
   âncora, para o título da seção não ficar escondido sob a barra */
function barraPresa() {
  const barra = document.querySelector(".filtros");
  new IntersectionObserver(([e]) => barra.classList.toggle("preso", !e.isIntersecting)).observe(
    document.getElementById("antes-filtros")
  );
  const folga = () => (document.documentElement.style.scrollPaddingTop = barra.offsetHeight + "px");
  new ResizeObserver(folga).observe(barra);
  folga();
}
function visiveis(pag) {
  return pag.P.reservatorios.filter(r => {
    const s = pag.sis[r.sistema];
    return (!pag.uf || r.uf === pag.uf) && (!pag.busca || semAcento(r.nome + " " + s.nome).includes(pag.busca));
  });
}
function limpar(pag) {
  pag.uf = pag.busca = "";
  document.getElementById("busca").value = "";
  aplicar(pag);
}
function aplicar(pag) {
  pag.vis = visiveis(pag);
  document.querySelectorAll("#presets-uf button").forEach(b => {
    b.classList.toggle("ativo", b.dataset.uf === pag.uf);
    b.setAttribute("aria-pressed", b.dataset.uf === pag.uf);
  });
  const n = pag.vis.length;
  const total = pag.P.reservatorios.length;
  document.getElementById("contagem").textContent = n === total ? "" : `${n} de ${total} açudes`;
  marcadores(pag);
  desenharVista(pag);
}

/* ---------- 1. mapa: triângulo = açude, sem cor por valor (regra do protótipo) ---------- */
function mapa(pag) {
  const host = document.getElementById("mapa-acudes");
  if (typeof L === "undefined") {
    host.outerHTML = '<p class="nota">O mapa não carregou neste ambiente.</p>';
    return;
  }
  const mp = L.map(host, { scrollWheelZoom: false, zoomSnap: 0.25 });
  const claro = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap", maxZoom: 18 }).addTo(mp);
  const satelite = L.layerGroup([
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Esri World Imagery",
      maxZoom: 18
    }),
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", { maxZoom: 18 })
  ]);
  L.control.layers({ "Mapa": claro, "Satélite": satelite }, null, { position: "topright" }).addTo(mp);
  const icone = L.divIcon({
    className: "acude-mapa",
    iconSize: [18, 16],
    iconAnchor: [9, 8],
    html: `<svg width="18" height="16" viewBox="0 0 18 16"><path d="M9 1 L17 15 L1 15 Z" fill="${COR.ana}" stroke="#ffffff" stroke-width="1.4"/></svg>`
  });
  const camada = L.layerGroup().addTo(mp);
  const marcas = {};
  pag.P.reservatorios.filter(r => r.lat != null).forEach(r => {
    const m = L.marker([r.lat, r.lon], { icon: icone, alt: r.nome });
    const med = r.medicao ? `${fmt(r.medicao.volume_pct)}% em ${dBR(r.medicao.data)}` : "sem informação";
    m.bindTooltip(`<div class="pop"><b>${esc(r.nome)} (${r.uf})</b>${esc(pag.sis[r.sistema].nome)}` +
      `<div class="l"><span>Volume</span><span>${med}</span></div></div>`, { direction: "top", offset: [0, -8], opacity: 1 });
    m.on("tooltipopen", e => dentroDoMapa(mp, m, e.tooltip));
    m.on("click", () => irPara(pag, r.res_id));
    marcas[r.res_id] = m;
  });
  // reenquadra nos açudes visíveis quando o filtro muda ou o contêiner muda de tamanho (enquanto o usuário não mexer)
  pag.mapa = { mp, camada, marcas, mexeu: false };
  mp.on("dragstart", () => (pag.mapa.mexeu = true));
  mp.getContainer().addEventListener("wheel", () => (pag.mapa.mexeu = true), { passive: true });
  mp.getContainer().querySelector(".leaflet-control-zoom").addEventListener("click", () => (pag.mapa.mexeu = true));
  new ResizeObserver(() => {
    mp.invalidateSize();
    if (!pag.mapa.mexeu) enquadrar(pag);
  }).observe(host);
  document.getElementById("baixar-kmz").addEventListener("click", () => baixarKMZ(pag));
}
// o tooltip do Leaflet não se reposiciona sozinho: perto da borda do mapa ele abre para baixo em vez de para cima e
// desliza na horizontal até caber, com a seta ainda apontando para o açude (no celular o mapa é estreito demais para
// abrir de lado)
function dentroDoMapa(mp, m, t) {
  const p = mp.latLngToContainerPoint(m.getLatLng());
  const tam = mp.getSize();
  const el = t.getElement();
  const w = el.offsetWidth, h = el.offsetHeight, borda = 4, vao = 12;
  const cimaCabe = p.y - h - vao >= borda, baixoCabe = p.y + h + vao <= tam.y - borda;
  const dir = cimaCabe || (!baixoCabe && p.y > tam.y / 2) ? "top" : "bottom";
  const dx = Math.max(borda - (p.x - w / 2), Math.min(0, tam.x - borda - (p.x + w / 2)));
  t.options.direction = dir;
  t.options.offset = [dx, dir === "top" ? -8 : 8];
  el.style.setProperty("--seta", Math.max(-w / 2 + 12, Math.min(w / 2 - 12, -dx)) + "px");
  t.update();
}
function marcadores(pag) {
  if (!pag.mapa) return;
  const { camada, marcas } = pag.mapa;
  camada.clearLayers();
  pag.vis.forEach(r => marcas[r.res_id] && camada.addLayer(marcas[r.res_id]));
  pag.mapa.mexeu = false;
  enquadrar(pag);
}
function enquadrar(pag) {
  const pts = (pag.vis || []).filter(r => r.lat != null);
  if (!pts.length) return;
  const b = L.latLngBounds(pts.map(r => [r.lat, r.lon]));
  pag.mapa.mp.fitBounds(b.pad(0.08), { maxZoom: 10, animate: false });
}
function irPara(pag, id) {
  if (pag.vista !== "sistemas") trocarVista(pag, "sistemas");
  const c = document.getElementById("acude-" + id);
  if (!c) return;
  c.scrollIntoView({ behavior: "smooth", block: "center" });
  document.querySelectorAll(".card.acude.destaque").forEach(x => x.classList.remove("destaque"));
  c.classList.add("destaque");
}

/* ---------- 2. açudes: por sistema hídrico (cartões) ou tabela ---------- */
function vistas(pag) {
  const v = document.getElementById("vistas");
  // em tela estreita "Por sistema hídrico" quebraria em duas linhas: o "hídrico" some (o nome acessível fica inteiro)
  const rotulo = t => t.replace(" hídrico", '<span class="so-largo"> hídrico</span>');
  v.innerHTML = VISTAS.map(([id, t]) => `<button type="button" role="tab" data-vista="${id}" aria-label="${t}">${ICONE[id]}${rotulo(t)}</button>`).join("");
  v.addEventListener("click", ev => {
    const b = ev.target.closest("button");
    if (b) trocarVista(pag, b.dataset.vista);
  });
  // setas do teclado trocam de aba, como em qualquer lista de abas
  v.addEventListener("keydown", ev => {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    const i = VISTAS.findIndex(([id]) => id === pag.vista);
    const j = (i + (ev.key === "ArrowRight" ? 1 : VISTAS.length - 1)) % VISTAS.length;
    trocarVista(pag, VISTAS[j][0]);
    v.querySelector(`[data-vista="${VISTAS[j][0]}"]`).focus();
  });
  document.getElementById("baixar-csv").addEventListener("click", () => baixarCSV(pag));
}
function trocarVista(pag, vista) {
  pag.vista = vista;
  lembrar("vista", vista);
  desenharVista(pag);
}
function desenharVista(pag) {
  document.querySelectorAll("#vistas button").forEach(b => {
    const sel = b.dataset.vista === pag.vista;
    b.setAttribute("aria-selected", sel);
    b.tabIndex = sel ? 0 : -1;
  });
  document.getElementById("dica-aba").textContent = VISTAS.find(([id]) => id === pag.vista)[2];
  const host = document.getElementById("lista-acudes");
  if (!pag.vis.length) {
    host.innerHTML = `<p class="vazio">Nenhum açude com esses filtros. <button type="button" class="acao sec" id="limpar">Limpar filtros</button></p>`;
    document.getElementById("limpar").addEventListener("click", () => limpar(pag));
    return;
  }
  host.innerHTML = pag.vista === "tabela" ? tabelaHTML(pag) : sistemasHTML(pag);
}
function cartaoAcude(r, pag) {
  const m = r.medicao;
  if (!m) {
    return `<div class="card fixo acude" id="acude-${r.res_id}"><div class="r">${esc(r.nome)}</div><div class="v sem">Sem informação</div>` +
      `<div class="n">Nenhuma medição nos últimos ${prazoBusca(pag)}</div></div>`;
  }
  const valor = m.volume_pct != null ? `${fmt(m.volume_pct)}<small>%</small>` : "–";
  const linhas = `<div class="n">${fmt(m.volume_hm3, 2)} de ${fmt(m.capacidade_hm3, 2)} hm³ · cota ${fmt(m.cota_m, 2)} m</div>` +
    `<div class="n">Medição de ${dBR(m.data)}${diasDesde(m.data) > 1 ? ` (há ${diasDesde(m.data)} dias)` : ""}</div>`;
  const alertas = r.alertas.filter(a => ALERTAS[a]).map(a => `<span class="alerta">${ALERTAS[a](r, pag)}</span>`).join("");
  return `<div class="card fixo acude" id="acude-${r.res_id}"><div class="r">${esc(r.nome)}</div><div class="v num">${valor}</div>${linhas}${alertas}</div>`;
}
function sistemasHTML(pag) {
  const porSis = {};
  pag.vis.forEach(r => (porSis[r.sistema] = porSis[r.sistema] || []).push(r));
  return pag.P.sistemas
    .filter(s => porSis[s.id])
    .sort((a, b) => a.ufs.localeCompare(b.ufs) || a.nome.localeCompare(b.nome, "pt-BR"))
    .map(s => {
      const b = s.boletim;
      return `<article class="sis"><h3>${esc(s.nome)} <span class="uf">${esc(s.ufs)}</span></h3>` +
        `<p class="links"><a class="acao sec" href="${esc(b.url)}">Boletim de ${esc(b.rotulo)} (PDF)</a>` +
        `<a href="${esc(s.pagina_comar)}">Termos e boletins anteriores</a></p>` +
        `<div class="cards">${porSis[s.id].map(r => cartaoAcude(r, pag)).join("")}</div>` + (s.nota ? `<p class="nota">${esc(s.nota)}</p>` : "") + `</article>`;
    })
    .join("");
}
function ordenadas(pag) {
  return [...pag.vis]
    .sort((a, b) => a.uf.localeCompare(b.uf) || a.nome.localeCompare(b.nome, "pt-BR"))
    .map(r => ({ r, s: pag.sis[r.sistema], m: r.medicao || {} }));
}
function tabelaHTML(pag) {
  return `<table id="tab-acudes"><thead><tr><th>Açude</th><th>UF</th><th>Sistema hídrico</th><th class="num">Volume</th>` +
    `<th class="num">Volume</th><th class="num">Cota</th><th class="num">Capacidade</th><th>Medição</th><th>Boletim</th></tr>` +
    `<tr class="unid"><th></th><th></th><th></th><th class="num">%</th><th class="num">hm³</th><th class="num">m</th><th class="num">hm³</th><th></th><th></th></tr></thead>` +
    `<tbody>${ordenadas(pag).map(({ r, s, m }, i, todas) =>
      `<tr${i && todas[i - 1].r.uf !== r.uf ? ' class="nova-uf"' : ""}><td><span class="nm">${esc(r.nome)}</span></td><td>${r.uf}</td><td>${esc(s.nome)}</td>` +
      `<td class="num">${fmt(m.volume_pct)}</td><td class="num">${fmt(m.volume_hm3, 2)}</td><td class="num">${fmt(m.cota_m, 2)}</td>` +
      `<td class="num">${fmt(m.capacidade_hm3, 2)}</td><td class="num">${m.data ? dBR(m.data) : "sem informação"}</td>` +
      `<td><a href="${esc(s.boletim.url)}" aria-label="Boletim de ${esc(s.boletim.rotulo)} de ${esc(s.nome)}">${mesCurto(s.boletim.mes)}</a></td></tr>`).join("")}</tbody></table>`;
}
/* CSV como no protótipo (salvarCSV): BOM, ';', vírgula decimal, data dd/mm/aaaa; leva o que está filtrado */
function baixarCSV(pag) {
  const n = (v, d) => (v == null ? "" : fmt(v, d).replace(/\./g, ""));
  const cab = ["codigo_sar", "acude", "uf", "sistema_hidrico", "volume_pct", "volume_hm3", "capacidade_hm3", "cota_m",
    "data_medicao", "observacao", "boletim", "pagina_alocacao"];
  const obs = r => (r.medicao ? r.alertas.filter(a => ALERTAS[a]).map(a => ALERTAS[a](r, pag)).join("; ")
    : `sem informação: nenhuma medição nos últimos ${prazoBusca(pag)}`);
  const linhas = ordenadas(pag).map(({ r, s, m }) => [r.res_id, r.nome, r.uf, s.nome, n(m.volume_pct, 2), n(m.volume_hm3, 2),
    n(m.capacidade_hm3, 2), n(m.cota_m, 2), m.data ? dBR(m.data) : "", obs(r), s.boletim.url, s.pagina_comar]);
  const q = v => (/[;"\n]/.test(String(v ?? "")) ? `"${String(v).replace(/"/g, '""')}"` : String(v ?? ""));
  const txt = [cab, ...linhas].map(l => l.map(q).join(";")).join("\r\n");
  baixarArquivo(new Blob(["﻿" + txt], { type: "text/csv;charset=utf-8" }), `acudes_alocacao_${pag.P.gerado_em.slice(0, 10)}.csv`);
}
function baixarArquivo(blob, nome) {
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: nome });
  document.body.appendChild(a);
  a.click();
  setTimeout(() => (URL.revokeObjectURL(a.href), a.remove()), 1000);
}

/* ---------- KMZ do mapa (o que está filtrado): ícone PNG com a forma e a cor da página ---------- */
function pngTriangulo(cor) {
  const c = Object.assign(document.createElement("canvas"), { width: 36, height: 32 });
  const g = c.getContext("2d");
  g.beginPath();
  g.moveTo(18, 2);
  g.lineTo(34, 30);
  g.lineTo(2, 30);
  g.closePath();
  g.fillStyle = cor;
  g.fill();
  g.lineWidth = 2.5;
  g.strokeStyle = "#ffffff";
  g.stroke();
  return c.toDataURL("image/png").split(",")[1];
}
async function baixarKMZ(pag) {
  if (typeof JSZip === "undefined") return;
  const zip = new JSZip();
  zip.file("icones/acude.png", pngTriangulo(COR.ana), { base64: true });
  const marcas = pag.vis.filter(r => r.lat != null).map(r => {
    const s = pag.sis[r.sistema];
    const m = r.medicao;
    const desc = `${s.nome}<br>${m ? `Volume ${fmt(m.volume_pct)}% em ${dBR(m.data)}` : "Sem informação"}<br>` +
      `<a href="${esc(s.boletim.url)}">Boletim de ${esc(s.boletim.rotulo)}</a>`;
    return `<Placemark><name>${esc(r.nome)}</name><description><![CDATA[${desc}]]></description><styleUrl>#acude</styleUrl>` +
      `<Point><coordinates>${r.lon},${r.lat},0</coordinates></Point></Placemark>`;
  }).join("");
  const kml = `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>` +
    `<name>Açudes com alocação de água (${dBR(pag.P.gerado_em)})</name>` +
    `<Style id="acude"><IconStyle><scale>1</scale><Icon><href>icones/acude.png</href></Icon></IconStyle></Style>${marcas}</Document></kml>`;
  zip.file("doc.kml", kml);
  baixarArquivo(await zip.generateAsync({ type: "blob" }), `acudes_alocacao_${pag.P.gerado_em.slice(0, 10)}.kmz`);
}

/* ---------- 3. sobre os dados (para o público: fontes e definições) ---------- */
function sobre(pag) {
  const f = pag.P.fontes;
  document.getElementById("sobre-corpo").innerHTML = `<dl>` +
    `<dt>Medições</dt><dd><a href="${esc(f.medicao.url)}">Sistema de Acompanhamento de Reservatórios (SAR)</a>, da ANA. ` +
    `O volume em % é o volume armazenado em relação à capacidade do açude, e a data é a da medição. Açude sem ` +
    `medição nos últimos ${janela(pag)} dias mostra a última disponível, com aviso; no SAR, ele aparece como sem ` +
    `informação.</dd>` +
    `<dt>Boletins</dt><dd>Publicados pela ANA na <a href="${esc(f.boletins.url)}">página de alocação de água e marcos ` +
    `regulatórios</a>, com os termos de alocação e os boletins anteriores de cada sistema.</dd></dl>`;
}

document.addEventListener("DOMContentLoaded", iniciar);
