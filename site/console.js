// Secure document Q&A console. Browser ports of mcp_server/ and agents/:
// retrieval.py (heading chunks + BM25Okapi), answer.py (extractive answer with [n] citations),
// policy.py (SHA-256 token hashes, per-tool scopes, deny by default), audit.py (hash chain),
// egress.py (outbound allowlist), planner.py and verifier.py. Data: python scripts/export_site.py
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---------- retrieval.py ----------
  const STOP = new Set("the a an and or of to in on for is are be with how what why do does should would you it that this by as".split(" "));
  const tokenize = (t) => (t.toLowerCase().match(/[a-z0-9]+/g) || []).filter((w) => !STOP.has(w));
  function chunkMarkdown(name, text) {
    const stem = name.replace(/\.[^.]+$/, ""), chunks = [];
    let section = stem, buf = [];
    const flush = () => { const body = buf.join(" ").split(/\s+/).filter(Boolean).join(" "); if (body) chunks.push({ id: `${stem}#${chunks.length + 1}`, source: name, section, text: body }); };
    for (const line of text.split(/\r?\n/)) {
      if (line.startsWith("#")) { flush(); buf = []; section = line.replace(/^#+/, "").trim(); } else buf.push(line);
    }
    flush();
    return chunks;
  }
  class BM25Okapi { // rank_bm25 defaults: k1=1.5, b=0.75, epsilon=0.25
    constructor(docs, k1 = 1.5, b = 0.75, eps = 0.25) {
      this.k1 = k1; this.b = b; this.len = docs.map((d) => d.length);
      this.avg = this.len.reduce((s, v) => s + v, 0) / docs.length;
      this.tf = docs.map((d) => { const m = new Map(); d.forEach((w) => m.set(w, (m.get(w) || 0) + 1)); return m; });
      const df = new Map(); this.tf.forEach((m) => m.forEach((_, w) => df.set(w, (df.get(w) || 0) + 1)));
      this.idf = new Map(); let sum = 0; const neg = [];
      df.forEach((n, w) => { const v = Math.log((docs.length - n + 0.5) / (n + 0.5)); this.idf.set(w, v); sum += v; if (v < 0) neg.push(w); });
      const floor = eps * (sum / Math.max(1, df.size)); neg.forEach((w) => this.idf.set(w, floor));
    }
    scores(q) {
      return this.tf.map((m, i) => q.reduce((s, w) => { const f = m.get(w) || 0; return s + (this.idf.get(w) || 0) * (f * (this.k1 + 1)) / (f + this.k1 * (1 - this.b + this.b * this.len[i] / this.avg)); }, 0));
    }
  }
  let DOCS = [], CHUNKS = [], INDEX = null;
  function reindex() {
    CHUNKS = DOCS.flatMap((d) => chunkMarkdown(d.name, d.text));
    INDEX = CHUNKS.length ? new BM25Okapi(CHUNKS.map((c) => tokenize(`${c.section} ${c.text}`))) : null;
    renderDocs();
  }
  function search(query, topK = 4) {
    const terms = tokenize(query);
    if (!terms.length || !INDEX) return [];
    const sc = INDEX.scores(terms);
    return CHUNKS.map((c, i) => ({ chunk: c, score: sc[i] })).sort((a, b) => b.score - a.score).slice(0, topK).filter((h) => h.score > 0);
  }

  // ---------- answer.py (extractive) ----------
  function extractive(query, hits, max = 3) {
    const terms = new Set(tokenize(query)), scored = [];
    hits.forEach((h, i) => h.chunk.text.split(/(?<=[.!?])\s+/).forEach((sent) => {
      const overlap = new Set(tokenize(sent).filter((w) => terms.has(w))).size;
      if (overlap) scored.push([overlap + h.score / 100, i + 1, sent.trim()]);
    }));
    scored.sort((a, b) => b[0] - a[0]);
    const picked = [], seen = new Set();
    for (const [, idx, sent] of scored) {
      if (!seen.has(sent)) { picked.push(`${sent} [${idx}]`); seen.add(sent); }
      if (picked.length === max) break;
    }
    return picked.join(" ");
  }

  // ---------- planner.py / verifier.py ----------
  function plan(task) {
    const words = new Set(task.toLowerCase().split(/\s+/));
    if (["audit", "log", "logs", "tamper", "chain"].some((w) => words.has(w)) && words.has("status")) return [["audit_status", { recent: 5 }]];
    return [["search_docs", { query: task, top_k: 4 }], ["rag_answer", { query: task }]];
  }
  function verify(tool, result, isError) {
    if (isError) return [false, "tool returned an error"];
    if (tool === "search_docs") return result.hits.length ? [true, `${result.hits.length} passages retrieved`] : [false, "no documents matched"];
    if (tool === "rag_answer") {
      const cited = new Set([...result.answer.matchAll(/\[(\d+)\]/g)].map((m) => +m[1]));
      const got = new Set(result.citations.map((c) => c.id));
      if (!cited.size) return [false, "answer contains no citations"];
      const extra = [...cited].filter((c) => !got.has(c));
      return extra.length ? [false, `cites sources that were not retrieved: ${extra}`] : [true, `grounded in sources ${[...cited].sort().join(", ")}`];
    }
    if (tool === "audit_status") return result.chain_ok ? [true, "audit chain intact"] : [false, "audit chain broken"];
    return [false, `no verifier for tool ${tool}`];
  }

  // ---------- policy.py ----------
  let POLICY = null;
  const sha256 = async (s) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)))].map((b) => b.toString(16).padStart(2, "0")).join("");
  async function authenticate(token) {
    const digest = await sha256(token);
    const t = POLICY.tokens.find((x) => x.token_sha256.toLowerCase() === digest);
    return t ? { client_id: t.client_id, scopes: new Set(t.scopes) } : null;
  }
  const allowed = (scopes, tool) => POLICY.tools[tool] !== undefined && scopes.has(POLICY.tools[tool]);

  // ---------- audit.py ----------
  const GENESIS = "0".repeat(64);
  const canonical = (o) => {
    if (o === null || typeof o !== "object") return JSON.stringify(o).replace(/[\u007f-￿]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));
    return "{" + Object.keys(o).sort().map((k) => JSON.stringify(k) + ":" + canonical(o[k])).join(",") + "}";
  };
  const AUDIT = [];
  async function record(tool, clientId, decision, args, latency, detail, corr) {
    const body = { ts: Date.now() / 1000, correlation_id: corr, tool, client_id: clientId, decision, args_sha256: await sha256(canonical(args || {})),
      latency_ms: latency == null ? null : Math.round(latency * 100) / 100, detail: detail || null, prev_hash: AUDIT.length ? AUDIT[AUDIT.length - 1].hash : GENESIS };
    body.hash = await sha256(canonical(body));
    AUDIT.push(body);
    renderAudit();
    return body;
  }
  async function verifyChain() {
    let prev = GENESIS;
    for (let i = 0; i < AUDIT.length; i++) {
      const { hash, ...rec } = AUDIT[i];
      if (rec.prev_hash !== prev) return { ok: false, records: AUDIT.length, broken_at: i + 1, reason: "prev_hash does not match previous record" };
      if ((await sha256(canonical(rec))) !== hash) return { ok: false, records: AUDIT.length, broken_at: i + 1, reason: "record contents were modified" };
      prev = hash;
    }
    return { ok: true, records: AUDIT.length };
  }
  function renderAudit(broken) {
    $("audit").innerHTML = AUDIT.slice().reverse().map((r, j) => {
      const i = AUDIT.length - j;
      return `<li class="${broken === i ? "broken" : ""}">#${i} <b>${esc(r.tool)}</b> <span class="${esc(r.decision)}">${esc(r.decision.toUpperCase())}</span> ${esc(r.client_id || "anonymous")}${r.detail ? ` · ${esc(r.detail)}` : ""}<span class="h">hash ${r.hash.slice(0, 24)}… prev ${r.prev_hash.slice(0, 12)}…</span></li>`;
    }).join("") || '<li>No records yet.</li>';
    $("chain-pill").textContent = `AUDIT: ${AUDIT.length} RECORD${AUDIT.length === 1 ? "" : "S"}`;
  }

  // ---------- egress.py ----------
  const realFetch = window.fetch.bind(window);
  const egressAllowed = (url) => { try { return new URL(url, location.href).origin === location.origin; } catch (_) { return false; } };
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : input.url;
    if (!egressAllowed(url)) {
      const host = (() => { try { return new URL(url).host; } catch (_) { return url; } })();
      record("egress", null, "deny", { host }, null, `blocked outbound connection to ${host}`, crypto.randomUUID());
      return Promise.reject(new Error(`zero-egress policy blocked connection to ${host}`));
    }
    return realFetch(input, init);
  };

  // ---------- the run ----------
  async function run(task) {
    task = task.trim();
    if (!task) return;
    const corr = crypto.randomUUID(), log = $("log");
    const w = log.querySelector(".welcome"); if (w) w.remove();
    const el = document.createElement("div");
    el.className = "run";
    el.innerHTML = `<div class="cmd">$ agent "${esc(task)}"</div><ul class="trace"></ul>`;
    log.appendChild(el);
    const trace = el.querySelector(".trace");
    const step = (cls, name, st, msg) => { trace.insertAdjacentHTML("beforeend", `<li class="${cls}"><i>${cls === "ok" ? "✓" : cls === "deny" ? "✕" : "•"}</i><span>${esc(name)}</span><span class="st">${st}</span><span>${msg}</span></li>`); log.scrollTop = log.scrollHeight; };
    const finish = (html, denied) => { el.insertAdjacentHTML("beforeend", `<div class="answer${denied ? " denied" : ""}">${html}</div>`); log.scrollTop = log.scrollHeight; };

    const cert = $("cert").value;
    if (cert !== "valid") {
      const why = cert === "none" ? "no client certificate presented" : "certificate verify failed: unknown CA";
      step("deny", "mTLS handshake", "FAIL", esc(why));
      await record("tls_handshake", null, "deny", {}, null, why, corr);
      return finish("The connection was refused before any request reached the server. Every client must present a certificate issued by the boundary's CA.", true);
    }
    step("ok", "mTLS handshake", "OK", "TLS 1.3, client certificate verified");
    const principal = await authenticate($("token").value);
    if (!principal) {
      step("deny", "bearer token", "401", "token hash not in policy");
      await record("authenticate", null, "deny", {}, null, "unknown token", corr);
      return finish("Unauthorized: the token's SHA-256 hash is not in the policy.", true);
    }
    step("ok", "bearer token", "OK", `${esc(principal.client_id)} · scopes: ${esc([...principal.scopes].join(", "))}`);
    const steps = plan(task);
    step("info", "planner", "PLAN", steps.map((s) => s[0]).join(" → "));
    let hits = [], answer = null;
    for (const [tool, args] of steps) {
      const t0 = performance.now();
      if (!allowed(principal.scopes, tool)) {
        step("deny", tool, "DENY", `needs scope ${esc(POLICY.tools[tool] || "(unlisted tool)")}`);
        await record(tool, principal.client_id, "deny", args, performance.now() - t0, "missing scope", corr);
        return finish(`<b>${esc(principal.client_id)}</b> is not allowed to call <code>${esc(tool)}</code>. Tools are denied unless the policy grants the scope.`, true);
      }
      let result;
      if (tool === "search_docs") { hits = search(args.query, args.top_k); result = { hits: hits.map((h) => ({ id: h.chunk.id, score: h.score })) }; }
      if (tool === "rag_answer") {
        hits = hits.length ? hits : search(args.query);
        answer = hits.length ? extractive(args.query, hits) : "No supporting documents were found for this question.";
        result = { answer, citations: hits.map((h, i) => ({ id: i + 1, chunk: h.chunk.id })) };
      }
      if (tool === "audit_status") { const rep = await verifyChain(); result = { chain_ok: rep.ok, records: rep.records, recent: AUDIT.slice(-5) }; }
      const ms = performance.now() - t0;
      await record(tool, principal.client_id, "allow", args, ms, null, corr);
      const [ok, why] = verify(tool, result, false);
      step(ok ? "ok" : "deny", tool, ok ? "ALLOW" : "REJECT", `${esc(why)} · ${ms.toFixed(1)} ms`);
      if (!ok) return finish(tool === "rag_answer" ? "The verifier rejected the answer because it is not grounded in retrieved sources, so nothing is shown. Try rephrasing, or add a document that covers it." : "No passage in the knowledge base matches that question. Add a document that covers it, or rephrase.", true);
      if (tool === "audit_status") return finish(`Audit chain <b class="good">intact</b>: ${result.records} records, each linked to the SHA-256 of the one before it.`);
      if (tool === "search_docs" && steps.length === 1) return;
    }
    if (answer !== null) {
      const html = esc(answer).replace(/\[(\d+)\]/g, (_, n) => `<sup title="${esc(hits[n - 1].chunk.source)} · ${esc(hits[n - 1].chunk.section)}">[${n}]</sup>`);
      finish(html);
      el.insertAdjacentHTML("beforeend", `<div class="sources">${hits.map((h, i) => `<details><summary>[${i + 1}] ${esc(h.chunk.source)} · ${esc(h.chunk.section)} · score ${h.score.toFixed(2)}</summary><p>${esc(h.chunk.text)}</p></details>`).join("")}</div>`);
    }
    if (principal.scopes.has("search_docs") && !principal.scopes.has("rag_answer") && hits.length) finish(`Read-only access: passages retrieved, but <code>rag_answer</code> is not in this token's scopes.`, true);
  }

  // ---------- UI ----------
  function renderDocs() {
    $("docs").innerHTML = DOCS.map((d, i) => `<li class="${d.yours ? "yours" : ""}"><b title="${esc(d.name)}">${esc(d.name)}</b><span>${chunkMarkdown(d.name, d.text).length} ch${d.yours ? ` <button type="button" data-rm="${i}" aria-label="Remove ${esc(d.name)}">✕</button>` : ""}</span></li>`).join("");
    $("kb-count").textContent = `${DOCS.length} docs · ${CHUNKS.length} chunks`;
  }
  $("docs").addEventListener("click", (e) => { const b = e.target.closest("[data-rm]"); if (b) { DOCS.splice(+b.dataset.rm, 1); reindex(); } });
  const addFiles = async (files) => {
    for (const f of files) { if (f.size > 2e6) continue; DOCS.push({ name: f.name, text: await f.text(), yours: true }); }
    reindex();
  };
  const drop = $("drop");
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => addFiles([...e.dataTransfer.files]));
  $("files").addEventListener("change", (e) => { addFiles([...e.target.files]); e.target.value = ""; });
  $("token-preset").addEventListener("change", (e) => {
    const custom = e.target.value === "custom";
    $("token").hidden = !custom;
    $("token").value = custom ? "" : e.target.value;
    if (custom) $("token").focus();
  });
  $("ask").addEventListener("submit", (e) => { e.preventDefault(); const q = $("q").value; $("q").value = ""; run(q); });
  $("verify").addEventListener("click", async () => {
    const r = await verifyChain();
    $("verify-out").innerHTML = r.ok ? `<span class="good">Chain intact · ${r.records} records</span>` : `<span class="bad">Broken at #${r.broken_at}: ${esc(r.reason)}</span>`;
    renderAudit(r.ok ? undefined : r.broken_at);
    $("chain-pill").classList.toggle("bad", !r.ok); $("chain-pill").classList.toggle("ok", r.ok);
  });
  $("tamper").addEventListener("click", () => {
    if (!AUDIT.length) { $("verify-out").textContent = "Run a question first so there is a record to edit."; return; }
    const i = Math.floor(AUDIT.length / 2);
    AUDIT[i].decision = AUDIT[i].decision === "allow" ? "deny" : "allow";
    renderAudit();
    $("verify-out").textContent = `Record #${i + 1}'s decision was edited. Now verify the chain.`;
  });
  $("egress").addEventListener("click", async () => {
    try { await fetch($("egress-url").value, { mode: "no-cors" }); $("egress-out").innerHTML = '<span class="good">Allowed: same-origin request.</span>'; }
    catch (err) { $("egress-out").innerHTML = `<span class="bad">${esc(err.message)}</span> The attempt is in the audit log.`; }
  });
  const TRY = ["How do I keep a model inside a zero-egress boundary?", "How should an MCP server authorize tool calls?", "Why hash the audit log?", "audit status"];
  $("try").innerHTML = TRY.map((t) => `<button type="button">${esc(t)}</button>`).join("");
  $("try").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) run(b.textContent); });

  Promise.all([realFetch("corpus.json").then((r) => r.json()), realFetch("policy.json").then((r) => r.json())]).then(([docs, pol]) => {
    DOCS = docs; POLICY = pol; reindex(); renderAudit();
  });
})();
