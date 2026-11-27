// Replays sessions recorded from the real server (site/runs.json).
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const GATES = ["Mutual TLS handshake", "Token to identity", "Scope check", "Tool runs inside the boundary", "Verifier checks citations", "Audit record appended"];

const SCENARIOS = {
  "Research agent": {
    run: "kms", ask: "How do workloads reach KMS without internet egress?",
    gates: [["pass", "Client certificate signed by the private CA"], ["pass", "research-agent"], ["pass", "search_docs, rag_answer allowed"],
      ["pass", "BM25 over 5 local documents, extractive answer"], ["pass", "Grounded in sources [1, 2]"], ["pass", "decision: allow"]],
  },
  "Second question": {
    run: "audit_q", ask: "Why are audit records hash-chained?",
    gates: [["pass", "Client certificate signed by the private CA"], ["pass", "research-agent"], ["pass", "search_docs, rag_answer allowed"],
      ["pass", "BM25 over 5 local documents, extractive answer"], ["pass", "Grounded in sources [1, 2, 3]"], ["pass", "decision: allow"]],
  },
  "Read-only agent": {
    run: "readonly", ask: "How do workloads reach KMS without internet egress?",
    gates: [["pass", "Client certificate signed by the private CA"], ["pass", "readonly-agent"], ["fail", "rag_answer requires scope 'rag_answer'"],
      ["skip", "Not reached"], ["skip", "Not reached"], ["pass", "decision: deny, with the reason"]],
    refusal: ["Access denied.", "The agent may search documents but may not ask for answers. Its search call succeeded; the answer call was refused and the refusal was written to the audit log."],
  },
  "Auditor": {
    run: "auditor", ask: "audit log status",
    gates: [["pass", "Client certificate signed by the private CA"], ["pass", "auditor"], ["pass", "audit_status allowed"],
      ["pass", "Recomputes every hash in the chain"], ["skip", "No citations needed"], ["pass", "decision: allow"]],
  },
  "Wrong token": {
    ask: "How do workloads reach KMS?",
    gates: [["pass", "Client certificate signed by the private CA"], ["fail", "HTTP 401 Unauthorized"], ["skip", "Not reached"],
      ["skip", "Not reached"], ["skip", "Not reached"], ["skip", "Rejected before any tool was named"]],
    refusal: ["401 Unauthorized.", "The token's SHA-256 hash matches nothing in the policy file. The server never learns which tool was wanted."],
  },
  "No certificate": {
    ask: "How do workloads reach KMS?",
    gates: [["fail", "Connection reset during the TLS handshake"], ["skip", "Not reached"], ["skip", "Not reached"],
      ["skip", "Not reached"], ["skip", "Not reached"], ["skip", "No HTTP request ever existed"]],
    refusal: ["Connection reset.", "Without a client certificate from the private CA, the TLS handshake fails. There is no HTTP request to log, which is the point."],
  },
  "Outbound call": {
    ask: "A tool tries to reach api.example.com",
    gates: [["pass", "Client certificate signed by the private CA"], ["pass", "research-agent"], ["pass", "Tool allowed"],
      ["fail", "socket.connect blocked: EgressBlocked"], ["skip", "Not reached"], ["pass", "Blocked destination recorded"]],
    refusal: ["Egress blocked.", "A process-wide socket guard allows loopback and the allowlist only. Any other connect raises before a packet leaves. From test_egress_guard_blocks_outbound_and_allows_loopback."],
  },
};

let RUNS = {};

function renderAnswer(r) {
  const used = new Set([...r.answer.matchAll(/\[(\d+)\]/g)].map((m) => +m[1]));
  const text = esc(r.answer).replace(/\s?\[(\d+)\]/g, "<sup>$1</sup>");
  const src = r.citations.map((c) => `<li class="${used.has(c.id) ? "" : "unused"}"><span>${esc(c.section)} <em>· ${esc(c.source)}</em></span><em>${c.score.toFixed(2)}</em></li>`).join("");
  return `<p class="answer">${text}</p><p class="q-caps">Retrieved passages · BM25 score</p><ol class="sources">${src}</ol>`;
}

function renderRecord(a) {
  if (!a) return "";
  const short = (h) => (h ? `${h.slice(0, 16)}…` : h);
  const lines = [
    `<b>client_id</b>    ${esc(a.client_id)}`, `<b>tool</b>         ${esc(a.tool)}`, `<b>decision</b>     ${esc(a.decision)}`,
    a.detail ? `<b>detail</b>       ${esc(a.detail)}` : null, `<b>args_sha256</b>  ${short(a.args_sha256)}`,
    `<b>prev_hash</b>    ${short(a.prev_hash)}`, `<b>hash</b>         ${short(a.hash)}`,
  ].filter(Boolean);
  return `<p class="q-caps">Audit record</p><pre class="record">${lines.join("\n")}</pre>`;
}

function show(name) {
  const s = SCENARIOS[name];
  document.querySelectorAll("#who button").forEach((b) => b.setAttribute("aria-pressed", String(b.textContent === name)));
  $("ask").textContent = s.ask;
  $("gates").innerHTML = s.gates.map(([st, note], i) =>
    `<li class="gate ${st}" style="animation-delay:${i * 90}ms"><i class="dot"></i><div><b>${GATES[i]}</b><span>${esc(note)}</span></div></li>`).join("");
  const run = s.run ? RUNS[s.run] : null;
  let html = "";
  if (s.refusal) html += `<p class="refusal">${s.refusal[0]}</p><p>${esc(s.refusal[1])}</p>`;
  else if (run && run.result && run.result.answer) html += renderAnswer(run.result);
  else if (run && run.result) html += `<p class="big-ok">Chain intact.</p><p class="q-small">${run.result.records} records verified, each against the hash of the one before it.</p><br/>`;
  html += renderRecord(run && run.audit);
  $("result").innerHTML = html;
}

$("who").innerHTML = Object.keys(SCENARIOS).map((n) => `<button aria-pressed="false">${n}</button>`).join("");
document.querySelectorAll("#who button").forEach((b) => b.addEventListener("click", () => show(b.textContent)));
fetch("runs.json").then((r) => r.json()).then((d) => { RUNS = d; show("Research agent"); });
