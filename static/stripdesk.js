"use strict";

const $ = selector => document.querySelector(selector);
const form = $("#settings");
const state = {strip: null, listing: [], frame: null, profile: null, sample: null, sheet: false, preview: 0};
const numeric = ["origin", "pitch", "count", "first", "top", "bottom", "dark_level", "dark_share"];
const colors = ["red", "green", "blue"];

async function api(path, params = {}) {
  const response = await fetch(path, params);
  const result = await response.json();
  if (!response.ok) throw Error(result.error?.message || result.error || result.message || "操作未完成");
  return result;
}

function json(method, value) {
  return {method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(value)};
}

function announce(message, error = false) {
  const banner = $("#status");
  banner.textContent = message;
  banner.dataset.error = error;
}

function run(action) {
  return event => {
    event.preventDefault();
    Promise.resolve().then(() => action(event)).catch(error => announce(error.message, true));
  };
}

function stripUrl(part = "", strip = state.strip) {
  return "/strip/strips/" + strip.id + part;
}

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function formatNumber(number) {
  return "#" + String(number).padStart(4, "0");
}

function button(label, action) {
  const item = node("button", label);
  item.type = "button";
  item.addEventListener("click", run(action));
  return item;
}

function library() {
  const items = state.listing.map(entry => {
    const item = button(entry.name, () => openStrip(entry.id));
    item.title = entry.name;
    item.setAttribute("aria-pressed", String(state.strip?.id === entry.id));
    return item;
  });
  $("#library").replaceChildren(...items);
}

function settings(config) {
  for (const name of numeric) form.elements[name].value = config[name];
  for (const [index, name] of colors.entries()) form.elements[name].value = config.base[index];
  form.elements.ratio.value = config.ratio;
  form.elements.negative.checked = config.negative;
}

function readSettings() {
  return {
    ...Object.fromEntries(numeric.map(name => [name, form.elements[name].valueAsNumber])),
    base: colors.map(name => form.elements[name].valueAsNumber),
    ratio: form.elements.ratio.value,
    negative: form.elements.negative.checked,
    revision: state.strip.revision,
  };
}

function drawProfile(profile) {
  const chart = $("#profile");
  const context = chart.getContext("2d");
  const w = chart.width;
  const h = chart.height;
  context.clearRect(0, 0, w, h);
  const scale = w / profile.fractions.length;
  context.fillStyle = "#475033";
  for (const band of profile.bands) context.fillRect(band.left * scale, 0, (band.right - band.left) * scale, h);
  context.strokeStyle = "#ddb080";
  context.setLineDash([6, 5]);
  context.beginPath();
  context.moveTo(0, h * (1 - profile.threshold));
  context.lineTo(w, h * (1 - profile.threshold));
  context.stroke();
  context.setLineDash([]);
  context.strokeStyle = "#e3e9a3";
  context.lineWidth = 1.5;
  context.beginPath();
  profile.fractions.forEach((value, index) => {
    const y = 2 + (h - 4) * (1 - value);
    if (index === 0) context.moveTo(0, y);
    else context.lineTo(index * scale, y);
  });
  context.stroke();
  $("#bands").textContent = profile.bands.map(band => band.left + "–" + band.right).join(" · ") || "当前暗值未找到连续暗带。";
}

function drawGuides() {
  if (!state.profile) return;
  const [width, height] = state.strip.size;
  const {top, bottom} = state.strip.config;
  const guides = state.profile.frames.map(frame => {
    const box = node("div", undefined, frame.number === state.frame ? "guide active" : "guide");
    box.style.cssText = `left:${frame.left / width * 100}%;width:${(frame.right - frame.left) / width * 100}%;top:${top / height * 100}%;height:${(bottom - top) / height * 100}%`;
    box.append(node("span", formatNumber(frame.number)));
    return box;
  });
  $("#guides").replaceChildren(...guides);
}

async function preview() {
  const seq = ++state.preview;
  const film = state.frame;
  const rev = "?rev=" + state.strip.revision;
  drawGuides();
  const controls = state.profile.frames.map(frame => {
    const item = button(formatNumber(frame.number), async () => {
      state.frame = frame.number;
      state.sheet = false;
      await preview();
    });
    item.setAttribute("aria-pressed", String(frame.number === film && !state.sheet));
    return item;
  });
  $("#frame-buttons").replaceChildren(...controls);
  $("#sheet-toggle").textContent = state.sheet ? "查看单帧" : "查看样片板";
  $("#transfer").disabled = state.sheet;
  if (state.sheet) {
    $("#frame-image").src = stripUrl("/contact.png") + rev;
    $("#frame-reading").textContent = "本条底片按片号排列的所有成片。";
    return;
  }
  const path = stripUrl("/frames/" + film);
  $("#frame-image").src = path + ".png" + rev;
  $("#frame-reading").textContent = "";
  const info = await api(path);
  if (seq !== state.preview) return;
  const box = info.aperture;
  const percent = value => (100 * value).toFixed(1) + "%";
  $("#frame-reading").textContent = `原片画幅 (${box[0]}, ${box[1]}) – (${box[2]}, ${box[3]}) · 暗部 ${percent(info.quality.shadows)} · 亮部 ${percent(info.quality.highlights)}`;
}

function displayRuns(rows, strip) {
  const items = rows.map(row => {
    const line = node("div", undefined, "run");
    line.append(node("span", `${row.created} · 第 ${row.strip_revision} 版 · ${row.frames.length} 张`));
    const link = node("a", "下载出片包");
    link.href = stripUrl("/runs/" + row.id + "/package.zip", strip);
    link.download = "";
    line.append(link);
    return line;
  });
  $("#runs").replaceChildren(...(items.length ? items : [node("p", "这条底片还没有保存的出片。")]));
}

async function display(strip, reset = true) {
  state.strip = strip;
  state.sample = null;
  $("#use-base").disabled = true;
  $("#probe").textContent = "在扫描图上点选像素，核对原色和转正颜色。";
  const [width, height] = strip.size;
  $("#strip-name").textContent = strip.name;
  $("#strip-meta").textContent = `${width} × ${height} px · 原片平均灰阶 ${strip.exposure.mean} · 第 ${strip.revision} 版${strip.synthetic ? " · 合成数据" : ""}`;
  const address = new URL(location.href);
  address.searchParams.set("strip", strip.id);
  history.replaceState(null, "", address);
  const source = $("#source");
  source.width = width;
  source.height = height;
  source.src = stripUrl("/source.png");
  settings(strip.config);
  const [profile, rows] = await Promise.all([api(stripUrl("/guides")), api(stripUrl("/runs"))]);
  if (state.strip !== strip) return;
  state.profile = profile;
  if (reset || !profile.frames.some(frame => frame.number === state.frame)) state.frame = profile.frames[0].number;
  if (reset) state.sheet = false;
  drawProfile(profile.profile);
  displayRuns(rows, strip);
  $("#desk").hidden = false;
  $("#blank").hidden = true;
  library();
  await preview();
}

let openSerial = 0;
async function openStrip(id) {
  const seq = ++openSerial;
  const strip = await api("/strip/strips/" + id);
  if (seq !== openSerial) return;
  await display(strip);
  if (seq === openSerial) announce("已打开片条。");
}

async function addStrip(request, path) {
  const value = await api(path, request);
  state.listing.unshift(value);
  await display(value);
  announce(value.synthetic ? "合成练习条已载入。" : "扫描图已导入。");
}

$("#upload").addEventListener("submit", run(async event => {
  const input = new FormData(event.currentTarget);
  await addStrip({method: "POST", body: input}, "/strip/strips");
  $("#upload").reset();
}));

$("#demo").addEventListener("click", run(() => addStrip({method: "POST"}, "/strip/demo")));

form.addEventListener("submit", run(async () => {
  const old = state.strip;
  const saved = await api(stripUrl(), json("PATCH", readSettings()));
  if (state.strip !== old) return;
  state.listing = state.listing.map(entry => entry.id === saved.id ? saved : entry);
  await display(saved, false);
  announce("已应用导线与成片设置。");
}));

$("#scan").addEventListener("click", run(async event => {
  const current = state.strip;
  const rect = $("#source").getBoundingClientRect();
  const [width, height] = current.size;
  const x = Math.min(width - 1, Math.max(0, Math.floor((event.clientX - rect.left) * width / rect.width)));
  const y = Math.min(height - 1, Math.max(0, Math.floor((event.clientY - rect.top) * height / rect.height)));
  const pixel = await api(stripUrl("/pixel?x=" + x + "&y=" + y));
  if (state.strip !== current) return;
  state.sample = pixel.base_sample;
  $("#use-base").disabled = false;
  $("#probe").textContent = `(${x}, ${y}) · 原色 ${pixel.raw.join(", ")} · 转正 ${pixel.positive.join(", ")}`;
}));

$("#use-base").addEventListener("click", () => {
  for (const [index, name] of colors.entries()) form.elements[name].value = state.sample[index];
  announce("片基已填入，应用设置后生效。");
});

$("#sheet-toggle").addEventListener("click", run(async () => {
  state.sheet = !state.sheet;
  await preview();
}));

$("#save-run").addEventListener("click", run(async () => {
  const current = state.strip;
  await api(stripUrl("/runs"), json("POST", {revision: current.revision}));
  const rows = await api(stripUrl("/runs", current));
  if (state.strip === current) displayRuns(rows, current);
  announce("出片已保存，可下载本版成片。");
}));

$("#transfer").addEventListener("click", run(async () => {
  const result = await api(stripUrl("/frames/" + state.frame + "/prepare"), {method: "POST"});
  location.href = result.url;
}));

api("/strip/strips").then(async listing => {
  state.listing = listing;
  library();
  const key = new URL(location.href).searchParams.get("strip");
  if (key && listing.some(strip => strip.id === key)) await openStrip(key);
}).catch(error => announce(error.message, true));
