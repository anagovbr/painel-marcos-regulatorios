/* Painel dos açudes com alocação de água e marco regulatório.
   Lê só o contrato dados/painel.json (gerado por coletor/atualiza.py) e desenha: título com o carimbo, mapa, açudes
   por sistema hídrico, tabela e fontes. Formatação e componentes seguem o protótipo do novo SAR (js/base.js,
   js/exportacao.js de dlpena/prototipo-sar-design). */
"use strict";

const COR = {};
const ESTADOS = {
  VERDE: { rot: "Verde", cls: "verde" },
  AMARELO: { rot: "Amarelo", cls: "amarelo" },
  VERMELHO: { rot: "Vermelho", cls: "vermelho" },
  AZUL: { rot: "Azul", cls: "azul" }
};
const ALERTAS = {
  sem_medicao: () => "Sem medição no SAR",
  medicao_antiga: r => `Última medição há ${diasDesde(r.medicao.data)} dias`,
  data_futura: () => "Data da medição no futuro: erro de carga no SAR",
  volume_fora_da_faixa: () => "Volume fora da faixa esperada"
};
const SECOES = [
  ["mapa", "Mapa"],
  ["acudes", "Açudes por sistema hídrico"],
  ["tabela", "Tabela"],
  ["fontes", "Fontes e critérios"]
];

/* ---------- utilitários (os do protótipo: fmt, dBR) ---------- */
const fmt = (v, n = 1) =>
  v == null || isNaN(v)
    ? "–"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: n, maximumFractionDigits: n });
const dBR = iso => iso.slice(8, 10) + "/" + iso.slice(5, 7) + "/" + iso.slice(0, 4);
const hBR = iso => dBR(iso) + ", " + iso.slice(11, 16);
const esc = s =>
  String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
// busca sem acento nem pontuação: "mae dagua" acha "Mãe d'Água"
const semAcento = s =>
  s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9 ]+/g, "").replace(/\s+/g, " ");
function diasDesde(iso) {
  const hoje = new Date();
  const d = new Date(iso + "T12:00:00");
  return Math.round((Date.UTC(hoje.getFullYear(), hoje.getMonth(), hoje.getDate()) - Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())) / 864e5);
}
function lerCores() {
  const cs = getComputedStyle(document.documentElement);
  for (const k of ["verde", "amarelo", "vermelho", "azul", "sem"]) COR[k] = cs.getPropertyValue(`--eh-${k}`).trim();
  COR.ana = cs.getPropertyValue("--ana").trim();
  COR.azul = cs.getPropertyValue("--ana-medio").trim();
}
const corEstado = e => COR[(ESTADOS[e] || { cls: "sem" }).cls];

/* ---------- partida ---------- */
async function iniciar() {
  lerCores();
  let P;
  try {
    const r = await fetch("dados/painel.json", { cache: "no-cache" });
    P = await r.json();
  } catch (e) {
    document.getElementById("carimbo").innerHTML = "<span>Não foi possível carregar os dados. Tente recarregar a página.</span>";
    return;
  }
  const pag = { P, sis: Object.fromEntries(P.sistemas.map(s => [s.id, s])), filtroUF: "", busca: "" };
  carimbo(pag);
  esqueleto(pag);
  indices();
  mapa(pag);
  acudes(pag);
  tabela(pag);
  fontes(pag);
}

function carimbo(pag) {
  const { P } = pag;
  document.getElementById("carimbo").innerHTML =
    `<span>Medições do SAR lidas em <b>${hBR(P.fontes.medicao.lido_em)}</b></span>` +
    `<span><b>${P.reservatorios.length}</b> açudes em <b>${P.sistemas.length}</b> sistemas hídricos</span>` +
    `<span>Boletins da COMAR até <b>${esc(P.criterio.rotulo)}</b></span>`;
}

function esqueleto(pag) {
  const sec = (id, n, titulo, sub, corpo, baixar = "") =>
    `<section class="cartao secao" id="${id}">${baixar}<h2><small>${n}</small>${titulo}</h2><p class="sub">${sub}</p>${corpo}</section>`;
  const btn = (id, rot) =>
    `<div class="baixar"><button type="button" id="${id}"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8M4.5 6.5 8 10l3.5-3.5M3 13h10" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>${rot}</button></div>`;
  document.getElementById("conteudo").innerHTML =
    `<nav class="indice" aria-label="Seções da página">${SECOES.map(([id, t]) => `<a href="#${id}">${t}</a>`).join("")}</nav>` +
    `<div class="intro"><p>A ANA acompanha, com os órgãos gestores estaduais e os usuários, a alocação de água de sistemas ` +
    `hídricos do Semiárido e, em vários deles, as regras do marco regulatório. Esta página reúne os açudes com boletim de ` +
    `acompanhamento recente: a última medição publicada no SAR, o estado hidrológico definido no termo de alocação e os ` +
    `links para o boletim, o termo e a resolução. Os documentos completos estão na <a href="${esc(pag.P.fontes.boletins.url)}">página de ` +
    `alocação de água e marcos regulatórios da ANA</a>.</p></div>` +
    sec("mapa", 1, "Mapa", "Cada triângulo é um açude, na cor do estado hidrológico definido no termo de alocação. " +
      "<span class=\"dica\">Passe o mouse para ver o volume; clique para ir ao cartão do açude.</span>",
      `<div id="mapa-acudes" role="region" aria-label="Mapa dos açudes"></div>`, btn("baixar-kmz", "KMZ")) +
    sec("acudes", 2, "Açudes por sistema hídrico", "Última medição publicada no SAR, estado hidrológico do termo e documentos de cada sistema.",
      `<div class="filtros"><div class="presets" id="presets-uf" role="group" aria-label="Filtrar por UF"></div>` +
      `<input type="search" id="busca" placeholder="Buscar açude ou sistema" aria-label="Buscar açude ou sistema"></div><div id="lista-sis"></div>`) +
    sec("tabela", 3, "Tabela", "Todos os açudes do painel, com a última medição publicada no SAR.",
      `<table id="tab-acudes"></table>`, btn("baixar-csv", "CSV")) +
    sec("fontes", 4, "Fontes e critérios", "De onde vem cada informação e quais açudes entram no painel.", `<div class="fontes" id="fontes-corpo"></div>`);
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

/* ---------- 1. mapa ---------- */
function icone(cor) {
  return L.divIcon({
    className: "acude-mapa",
    iconSize: [18, 16],
    iconAnchor: [9, 8],
    html: `<svg width="18" height="16" viewBox="0 0 18 16"><path d="M9 1 L17 15 L1 15 Z" fill="${cor}" stroke="#ffffff" stroke-width="1.4"/></svg>`
  });
}
function rotuloEstado(r) {
  return ESTADOS[r.estado] ? `Estado hidrológico no termo: ${ESTADOS[r.estado].rot}` : "Sem estado hidrológico no termo";
}
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
  const pts = pag.P.reservatorios.filter(r => r.lat != null);
  pts.forEach(r => {
    const m = L.marker([r.lat, r.lon], { icon: icone(corEstado(r.estado)), alt: r.nome }).addTo(mp);
    const med = r.medicao ? `${fmt(r.medicao.volume_pct)}% em ${dBR(r.medicao.data)}` : "sem medição no SAR";
    m.bindTooltip(`<div class="pop"><b>${esc(r.nome)} (${r.uf})</b>${esc(pag.sis[r.sistema].nome)}<div class="l"><span>Volume</span><span>${med}</span></div>` +
      `<div class="l"><span>${rotuloEstado(r)}</span></div></div>`, { direction: "top", offset: [0, -8], opacity: 1 });
    m.on("click", () => irPara(r.res_id));
  });
  // reenquadra quando o contêiner muda de tamanho (carga, giro do celular), enquanto o usuário não mexer no mapa
  const limites = L.latLngBounds(pts.map(r => [r.lat, r.lon])).pad(0.08);
  let mexeu = false;
  mp.on("dragstart", () => (mexeu = true));
  mp.getContainer().addEventListener("wheel", () => (mexeu = true), { passive: true });
  mp.getContainer().querySelector(".leaflet-control-zoom").addEventListener("click", () => (mexeu = true));
  new ResizeObserver(() => {
    mp.invalidateSize();
    if (!mexeu) mp.fitBounds(limites);
  }).observe(host);
  mp.fitBounds(limites);
  legendaMapa(mp);
  document.getElementById("baixar-kmz").addEventListener("click", () => baixarKMZ(pag));
}
function legendaMapa(mp) {
  const leg = L.control({ position: "bottomleft" });
  leg.onAdd = () => {
    const d = L.DomUtil.create("div", "legenda-mapa");
    d.innerHTML =
      `<b>Estado hidrológico</b><span class="nota">definido no termo de alocação da campanha</span>` +
      ["VERDE", "AMARELO", "VERMELHO"].map(e => `<i class="tri" style="background:${corEstado(e)}"></i>${ESTADOS[e].rot}<br>`).join("") +
      `<i class="tri" style="background:${COR.sem}"></i>Sem estado no termo`;
    return d;
  };
  leg.addTo(mp);
}
function irPara(id) {
  const c = document.getElementById("acude-" + id);
  if (!c) return;
  if (c.closest(".sis").hidden) limparFiltros();
  c.scrollIntoView({ behavior: "smooth", block: "center" });
  document.querySelectorAll(".card.acude.destaque").forEach(x => x.classList.remove("destaque"));
  c.classList.add("destaque");
}

/* ---------- 2. açudes por sistema ---------- */
function cartaoAcude(r) {
  const m = r.medicao;
  const e = ESTADOS[r.estado];
  const valor = m && m.volume_pct != null ? `${fmt(m.volume_pct)}<small>%</small>` : "–";
  const linhas = m
    ? `<div class="n">${fmt(m.volume_hm3, 2)} de ${fmt(m.capacidade_hm3, 2)} hm³ · cota ${fmt(m.cota_m, 2)} m</div>` +
      `<div class="n">Medição de ${dBR(m.data)}${diasDesde(m.data) > 1 ? ` (há ${diasDesde(m.data)} dias)` : ""}</div>`
    : "";
  const alertas = r.alertas.map(a => `<span class="alerta">${ALERTAS[a] ? ALERTAS[a](r) : a}</span>`).join("");
  const det = [r.estado_detalhe, r.estado_data_ref && `volume de referência em ${r.estado_data_ref}`, r.estado_fonte]
    .filter(Boolean).join("; ");
  const eh = e
    ? `<div class="eh ${e.cls}"><b>Estado hidrológico ${e.rot.toLowerCase()}</b><small>${esc(det)}</small></div>`
    : `<div class="eh"><b>Sem estado hidrológico</b><small>${esc(r.estado_detalhe || "não definido no termo")}</small></div>`;
  return `<div class="card fixo acude" id="acude-${r.res_id}"><div class="r">${esc(r.nome)}</div><div class="v num">${valor}</div>${linhas}${alertas}${eh}</div>`;
}
function blocoSistema(s, rs) {
  const b = s.boletim;
  const meta = [
    s.campanha ? `Alocação ${s.campanha}${s.vigencia ? `, vigência de ${esc(s.vigencia)}` : ""}` : "",
    s.marco ? `Marco regulatório: ${s.marco_link ? `<a href="${esc(s.marco_link)}">${esc(s.marco)}</a>` : esc(s.marco)}` : ""
  ].filter(Boolean).join(" · ");
  const links = [
    `<a class="acao sec" href="${esc(b.url)}">Boletim de ${esc(b.rotulo)} (PDF)</a>`,
    `<a href="${esc(s.pagina_comar)}">Página da alocação</a>`,
    s.termo_link ? `<a href="${esc(s.termo_link)}">Termo de alocação ${esc(s.campanha)} (PDF)</a>` : ""
  ].filter(Boolean).join("");
  return `<article class="sis" data-ufs="${esc(s.ufs)}" data-busca="${esc(semAcento(s.nome + " " + rs.map(r => r.nome).join(" ")))}">` +
    `<h3>${esc(s.nome)} <span class="uf">${esc(s.ufs)}</span></h3>${meta ? `<p class="meta">${meta}</p>` : ""}` +
    `<p class="links">${links}</p><div class="cards">${rs.map(cartaoAcude).join("")}</div>` +
    (s.nota ? `<p class="nota">${esc(s.nota)}</p>` : "") + `</article>`;
}
function acudes(pag) {
  const porSis = {};
  pag.P.reservatorios.forEach(r => (porSis[r.sistema] = porSis[r.sistema] || []).push(r));
  const ordem = [...pag.P.sistemas].sort((a, b) => a.ufs.localeCompare(b.ufs) || a.nome.localeCompare(b.nome, "pt-BR"));
  document.getElementById("lista-sis").innerHTML = ordem.map(s => blocoSistema(s, porSis[s.id])).join("");
  const ufs = [...new Set(pag.P.reservatorios.map(r => r.uf))].sort();
  const pres = document.getElementById("presets-uf");
  pres.innerHTML = [["", "Todas as UFs"], ...ufs.map(u => [u, u])]
    .map(([v, t]) => `<button type="button" class="preset${v === "" ? " ativo" : ""}" data-uf="${v}">${t}</button>`).join("");
  pres.addEventListener("click", ev => {
    const b = ev.target.closest("button");
    if (!b) return;
    pag.filtroUF = b.dataset.uf;
    pres.querySelectorAll("button").forEach(x => x.classList.toggle("ativo", x === b));
    filtrar(pag);
  });
  document.getElementById("busca").addEventListener("input", ev => {
    pag.busca = semAcento(ev.target.value.trim());
    filtrar(pag);
  });
  pag.limpar = () => {
    pag.filtroUF = pag.busca = "";
    document.getElementById("busca").value = "";
    pres.querySelectorAll("button").forEach(x => x.classList.toggle("ativo", x.dataset.uf === ""));
    filtrar(pag);
  };
  limparFiltros = pag.limpar;
}
let limparFiltros = () => {};
function filtrar(pag) {
  document.querySelectorAll("#lista-sis .sis").forEach(el => {
    const okUF = !pag.filtroUF || el.dataset.ufs.includes(pag.filtroUF);
    el.hidden = !(okUF && (!pag.busca || el.dataset.busca.includes(pag.busca)));
  });
}

/* ---------- 3. tabela e CSV ---------- */
function linhasTabela(pag) {
  return [...pag.P.reservatorios]
    .sort((a, b) => a.uf.localeCompare(b.uf) || a.nome.localeCompare(b.nome, "pt-BR"))
    .map(r => ({ r, s: pag.sis[r.sistema], m: r.medicao || {} }));
}
function tabela(pag) {
  const L_ = linhasTabela(pag);
  document.getElementById("tab-acudes").innerHTML =
    `<thead><tr><th>Açude</th><th>UF</th><th>Sistema hídrico</th><th class="num">Volume</th><th class="num">Volume</th>` +
    `<th class="num">Cota</th><th class="num">Capacidade</th><th>Medição</th><th>Estado no termo</th></tr>` +
    `<tr class="unid"><th></th><th></th><th></th><th class="num">%</th><th class="num">hm³</th><th class="num">m</th><th class="num">hm³</th><th></th><th></th></tr></thead>` +
    `<tbody>${L_.map(({ r, s, m }) =>
      `<tr><td><span class="nm">${esc(r.nome)}</span></td><td>${r.uf}</td><td>${esc(s.nome)}</td>` +
      `<td class="num">${fmt(m.volume_pct)}</td><td class="num">${fmt(m.volume_hm3, 2)}</td><td class="num">${fmt(m.cota_m, 2)}</td>` +
      `<td class="num">${fmt(m.capacidade_hm3, 2)}</td><td class="num">${m.data ? dBR(m.data) : "sem medição"}</td>` +
      `<td><span class="eh-ponto" style="background:${corEstado(r.estado)}"></span>${ESTADOS[r.estado] ? ESTADOS[r.estado].rot : "—"}</td></tr>`).join("")}</tbody>`;
  document.getElementById("baixar-csv").addEventListener("click", () => baixarCSV(pag));
}
/* CSV como no protótipo (salvarCSV): BOM, ';', vírgula decimal, data dd/mm/aaaa */
function baixarCSV(pag) {
  const n = (v, d) => (v == null ? "" : fmt(v, d).replace(/\./g, ""));
  const cab = ["codigo_sar", "acude", "uf", "sistema_hidrico", "volume_pct", "volume_hm3", "capacidade_hm3", "cota_m",
    "data_medicao", "estado_hidrologico_termo", "estado_data_referencia", "boletim", "termo_alocacao", "marco_regulatorio"];
  const linhas = linhasTabela(pag).map(({ r, s, m }) => [r.res_id, r.nome, r.uf, s.nome, n(m.volume_pct, 2), n(m.volume_hm3, 2),
    n(m.capacidade_hm3, 2), n(m.cota_m, 2), m.data ? dBR(m.data) : "", r.estado, r.estado_data_ref, s.boletim.url, s.termo_link, s.marco]);
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

/* ---------- KMZ do mapa: ícones PNG com a forma e a cor da página e a legenda como sobreposição ---------- */
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
  const cls = e => (ESTADOS[e] || { cls: "sem" }).cls;
  ["verde", "amarelo", "vermelho", "azul", "sem"].forEach(k => zip.file(`icones/${k}.png`, pngTriangulo(COR[k]), { base64: true }));
  const estilos = ["verde", "amarelo", "vermelho", "azul", "sem"]
    .map(k => `<Style id="${k}"><IconStyle><scale>1</scale><Icon><href>icones/${k}.png</href></Icon></IconStyle></Style>`).join("");
  const marcas = pag.P.reservatorios.filter(r => r.lat != null).map(r => {
    const s = pag.sis[r.sistema];
    const m = r.medicao;
    const desc = `${s.nome}<br>${m ? `Volume ${fmt(m.volume_pct)}% em ${dBR(m.data)}` : "Sem medição no SAR"}<br>${rotuloEstado(r)}<br>` +
      `<a href="${esc(s.boletim.url)}">Boletim de ${esc(s.boletim.rotulo)}</a>`;
    return `<Placemark><name>${esc(r.nome)}</name><description><![CDATA[${desc}]]></description><styleUrl>#${cls(r.estado)}</styleUrl>` +
      `<Point><coordinates>${r.lon},${r.lat},0</coordinates></Point></Placemark>`;
  }).join("");
  const kml = `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>` +
    `<name>Açudes com alocação de água (${dBR(pag.P.gerado_em)})</name>${estilos}${marcas}</Document></kml>`;
  zip.file("doc.kml", kml);
  baixarArquivo(await zip.generateAsync({ type: "blob" }), `acudes_alocacao_${pag.P.gerado_em.slice(0, 10)}.kmz`);
}

/* ---------- 4. fontes e critérios ---------- */
function fontes(pag) {
  const { P } = pag;
  const f = P.fontes;
  document.getElementById("fontes-corpo").innerHTML = `<dl>` +
    `<dt>Medição dos açudes</dt><dd><a href="${esc(f.medicao.url)}">${esc(f.medicao.nome)}</a>: última medição publicada de cada açude, ` +
    `lida em ${hBR(f.medicao.lido_em)}. O volume em % é o volume armazenado dividido pela capacidade do açude no SAR. ` +
    `A data ao lado de cada valor é a da medição, que pode ser anterior à leitura.</dd>` +
    `<dt>Boletins, termos e resoluções</dt><dd><a href="${esc(f.boletins.url)}">${esc(f.boletins.nome)}</a>, lida em ${hBR(f.boletins.lido_em)}.</dd>` +
    `<dt>Quais açudes entram</dt><dd>Os açudes que têm página no boletim de acompanhamento da alocação de água publicado pela ANA ` +
    `nos ${P.criterio.janela_meses} meses anteriores ao boletim mais recente (${esc(P.criterio.rotulo)}). Quando sai um boletim novo, ` +
    `o açude entra; quando o boletim deixa de sair, o açude sai do painel.</dd>` +
    `<dt>Estado hidrológico</dt><dd>O declarado no termo de alocação da campanha para cada açude, a partir do volume na data de ` +
    `referência indicada no termo. Vale para toda a campanha e não é recalculado com a medição atual. Sem termo publicado, o ` +
    `açude aparece sem estado.</dd></dl>`;
}

document.addEventListener("DOMContentLoaded", iniciar);
