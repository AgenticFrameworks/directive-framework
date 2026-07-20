#!/usr/bin/env node
// directives-runtime.mjs — deterministic, fail-closed runtime for the native
// directive pipeline fused into the pi agent harness.
//
// This is the executable substrate the pi extension (directives.ts) shells out
// to. It owns every state transition the framework trusts: cursor writes,
// registry appends, packet validation, phase-gate checks, and lane overlap
// detection. The extension NEVER trusts the model with these writes — it
// routes every mutation through this script, exactly as the directive
// framework's EXECUTOR-SPEC owns the apply/synthesis mechanics.
//
// Contract mirror of the directive-framework canon (RUNTIME-SPEC.md,
// GATES-SPEC.md, EXECUTOR-SPEC.md), re-homed natively into pi:
//   - runtime dir per project: ~/.pi/agent/directives/<slug>/
//   - cursor.json: phase/role/active_directive/boundary/lane (atomic replace)
//   - registry.jsonl: append-only status registry
//   - PD/ DD/ VD/ ED/ RD/ packet directories
//   - phases: planning -> design -> validation -> execution -> review
//   - states: DRAFT | VETTED | GREENLIT | BUILT-GREEN | BUILT-RED | VERIFIED | REOPENED
//   - gate exit codes: 0 PASS / 1 BOUNCE / 2 BLOCK (fail-closed)
//
// Usage: see `node directives-runtime.mjs help`.

import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawnSync } from "node:child_process";

const PI_AGENT = process.env.PI_CODING_AGENT_DIR || path.join(os.homedir(), ".pi/agent");
// Honor DIRECTIVES_RUNTIME_DIR so an installed pi package and the in-place
// build share the same per-project runtime root (the extension sets the same
// env when it shells out). Default: ~/.pi/agent/directives/.
const RUNTIME_ROOT = process.env.DIRECTIVES_RUNTIME_DIR || path.join(PI_AGENT, "directives");

const PHASES = ["planning", "design", "validation", "execution", "review"];
const PHASE_ORDER = Object.fromEntries(PHASES.map((p, i) => [p, i]));
const STATES = new Set([
  "DRAFT", "VETTED", "GREENLIT", "BUILT-GREEN", "BUILT-RED", "VERIFIED", "REOPENED",
]);
const PACKET_KINDS = new Set(["PD", "DD", "VD", "ED", "RD"]);
const ID_RE = /^(PD|DD|VD|ED|RD)-(\d{3})$/;

// ---------- helpers ----------

function die(code, msg) {
  process.stderr.write(String(msg) + "\n");
  process.exit(code);
}

function now() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function slugFor(cwd) {
  if (!cwd) return "_global";
  const base = path.basename(path.resolve(cwd));
  const safe = base.replace(/[^a-zA-Z0-9._-]/g, "_");
  // disambiguate same-named dirs by a short hash of the full path
  let h = 0;
  for (const ch of cwd) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return `${safe || "_root"}-${(h >>> 0).toString(36).slice(-4)}`;
}

function runtimeDir(cwd) {
  return path.join(RUNTIME_ROOT, slugFor(cwd));
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function atomicWrite(file, content) {
  ensureDir(path.dirname(file));
  const tmp = file + ".tmp." + process.pid;
  fs.writeFileSync(tmp, content);
  fs.renameSync(tmp, file);
}

function readJson(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return fallback;
  }
}

// exclusive-create: never clobber existing runtime state (ED-003 init precedent)
function exclusiveCreate(file, content) {
  ensureDir(path.dirname(file));
  let fd;
  try {
    fd = fs.openSync(file, "wx");
  } catch (e) {
    if (e.code === "EEXIST") return false;
    throw e;
  }
  try {
    fs.writeFileSync(fd, content);
  } finally {
    fs.closeSync(fd);
  }
  return true;
}

function validId(id) {
  return ID_RE.test(id || "");
}

function kindOf(id) {
  return validId(id) ? id.slice(0, 2) : null;
}

function serialOf(id) {
  const m = ID_RE.exec(id || "");
  return m ? Number(m[2]) : -1;
}

function nextSerial(dirs) {
  let max = 0;
  for (const d of dirs) {
    if (!fs.existsSync(d)) continue;
    for (const name of fs.readdirSync(d)) {
      const m = ID_RE.exec(name.replace(/\.md$/, ""));
      if (m) max = Math.max(max, Number(m[2]));
    }
  }
  return max + 1;
}

function pad3(n) {
  return String(n).padStart(3, "0");
}

// ---------- commands ----------

function cmdInit(args) {
  const cwd = args[0] || process.cwd();
  const dir = runtimeDir(cwd);
  const made = exclusiveCreate(path.join(dir, "registry.jsonl"), "");
  const cursorPath = path.join(dir, "cursor.json");
  if (made || !fs.existsSync(cursorPath)) {
    atomicWrite(cursorPath, JSON.stringify({
      phase: "planning",
      role: "orchestrator",
      active_directive: null,
      boundary: null,
      lane: null,
      postpones_used: 0,
      updated: now(),
      updated_by: "init",
    }, null, 2) + "\n");
  }
  for (const k of PACKET_KINDS) ensureDir(path.join(dir, k));
  ensureDir(path.join(dir, "lanes"));
  process.stdout.write(JSON.stringify({ dir, cursor: cursorPath, slug: slugFor(cwd) }) + "\n");
}

function cmdDir(args) {
  const cwd = args[0] || process.cwd();
  process.stdout.write(runtimeDir(cwd) + "\n");
}

function cmdCursor(args) {
  const cwd = args[0] || process.cwd();
  const file = path.join(runtimeDir(cwd), "cursor.json");
  const cur = readJson(file, null);
  if (!cur) die(2, `no cursor at ${file}; run init first`);
  // validate shape (RUNTIME-SPEC strict-ish)
  const errs = [];
  if (!PHASES.includes(cur.phase)) errs.push(`bad phase: ${cur.phase}`);
  if (!["orchestrator", "author", "coder", "reviewer", "idle"].includes(cur.role)) errs.push(`bad role: ${cur.role}`);
  if (cur.active_directive !== null && !validId(cur.active_directive)) errs.push(`bad active_directive: ${cur.active_directive}`);
  if (typeof cur.postpones_used !== "number") errs.push(`bad postpones_used`);
  if (errs.length) die(2, `cursor invalid:\n  ${errs.join("\n  ")}`);
  process.stdout.write(JSON.stringify(cur, null, 2) + "\n");
}

// sanctioned cursor writer — the ONLY path that mutates cursor.json
function cmdSetCursor(args) {
  // set-cursor <cwd> <phase> <role> <active_directive|-> [boundary] [lane]
  const [cwd, phase, role, active, boundary, lane] = args;
  if (!PHASES.includes(phase)) die(2, `bad phase: ${phase}`);
  if (!["orchestrator", "author", "coder", "reviewer", "idle"].includes(role)) die(2, `bad role: ${role}`);
  const dir = runtimeDir(cwd);
  const file = path.join(dir, "cursor.json");
  const cur = readJson(file, null);
  if (!cur) die(2, `no cursor at ${file}; run init first`);
  const ad = active === "-" || active === "" ? null : active;
  if (ad !== null && !validId(ad)) die(2, `bad active_directive: ${ad}`);
  // phase change resets postpones_used (AUTO-HANDOFF-SPEC reset ownership)
  const phaseChanged = cur.phase !== phase;
  const next = {
    ...cur,
    phase,
    role,
    active_directive: ad,
    boundary: boundary === "-" || !boundary ? null : boundary,
    lane: lane === "-" || !lane ? null : lane,
    postpones_used: phaseChanged ? 0 : cur.postpones_used ?? 0,
    updated: now(),
    updated_by: "extension",
  };
  atomicWrite(file, JSON.stringify(next, null, 2) + "\n");
  process.stdout.write(JSON.stringify(next) + "\n");
}

function cmdPostpone(args) {
  // postpone <cwd> — increment postpones_used; refuse at budget (2)
  const [cwd] = args;
  const dir = runtimeDir(cwd);
  const file = path.join(dir, "cursor.json");
  const cur = readJson(file, null);
  if (!cur) die(2, `no cursor at ${file}`);
  const BUDGET = 2;
  if ((cur.postpones_used ?? 0) >= BUDGET) {
    die(2, `postpone budget exhausted (${BUDGET}); escalate to human (HiTL)`);
  }
  const next = { ...cur, postpones_used: (cur.postpones_used ?? 0) + 1, updated: now() };
  atomicWrite(file, JSON.stringify(next, null, 2) + "\n");
  process.stdout.write(JSON.stringify({ postpones_used: next.postpones_used }) + "\n");
}

function readRegistry(dir) {
  const file = path.join(dir, "registry.jsonl");
  if (!fs.existsSync(file)) return [];
  return fs.readFileSync(file, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line, i) => {
      try { return JSON.parse(line); } catch { return { _bad: i, _line: line }; }
    });
}

function latestLine(reg, id) {
  let latest = null;
  for (const l of reg) {
    if (l && l.id === id) latest = l;
  }
  return latest;
}

function cmdRegistry(args) {
  // registry <cwd> [id]
  const [cwd, id] = args;
  const dir = runtimeDir(cwd);
  const reg = readRegistry(dir);
  if (id) {
    process.stdout.write(JSON.stringify(latestLine(reg, id) || null, null, 2) + "\n");
  } else {
    for (const l of reg) process.stdout.write(JSON.stringify(l) + "\n");
  }
}

// append-registry — flock'd, line-validated (ED-060 single append path)
async function cmdAppend(args) {
  // append <cwd> <json>
  const [cwd, json] = args;
  const dir = runtimeDir(cwd);
  const file = path.join(dir, "registry.jsonl");
  let entry;
  try { entry = JSON.parse(json); } catch { die(2, "bad registry entry json"); }
  if (!validId(entry.id)) die(2, `bad id: ${entry.id}`);
  if (!STATES.has(entry.state)) die(2, `bad state: ${entry.state}`);
  entry.ts = entry.ts || now();
  // flock via a lock directory (mkdir is atomic on POSIX) — the single append
  // path (ED-060 id-collision class)
  const lockFile = path.join(dir, "registry.lock");
  let acquired = false;
  for (let i = 0; i < 60; i++) {
    try { fs.mkdirSync(lockFile); acquired = true; break; } catch (e) {
      if (e.code !== "EEXIST") die(2, `lock error: ${e.message}`);
      // stale lock sweep (30s)
      try {
        const st = fs.statSync(lockFile);
        if (Date.now() - st.mtimeMs > 30000) fs.rmSync(lockFile, { recursive: true });
      } catch {}
      await sleep(50);
    }
  }
  if (!acquired) die(2, "registry lock contention; retry");
  try {
    const line = JSON.stringify(entry) + "\n";
    fs.appendFileSync(file, line);
    process.stdout.write(line.trim() + "\n");
  } finally {
    fs.rmSync(lockFile, { recursive: true });
  }
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

// greenlight gate: latest line for id must be GREENLIT with go_basis (EXECUTOR-SPEC §1)
function cmdGreenlight(args) {
  // greenlight <cwd> <id> <go_basis>
  const [cwd, id, goBasis] = args;
  if (!validId(id)) die(2, `bad id: ${id}`);
  if (!goBasis) die(2, "go_basis required (human:<name> | delegated:<basis> | envelope:<version>)");
  const dir = runtimeDir(cwd);
  const reg = readRegistry(dir);
  const prev = latestLine(reg, id);
  // GREENLIT requires a prior VETTED line (no skipping the gate)
  if (!prev || prev.state !== "VETTED") {
    die(2, `cannot greenlight ${id}: latest state is ${prev ? prev.state : "(none)"}, need VETTED`);
  }
  cmdAppend([cwd, JSON.stringify({ id, state: "GREENLIT", go_basis: goBasis })]);
}

function cmdVetted(args) {
  // vetted <cwd> <id>
  const [cwd, id] = args;
  if (!validId(id)) die(2, `bad id: ${id}`);
  const dir = runtimeDir(cwd);
  const reg = readRegistry(dir);
  const prev = latestLine(reg, id);
  if (prev && prev.state === "GREENLIT") die(2, `${id} already greenlit; no re-vet`);
  cmdAppend([cwd, JSON.stringify({ id, state: "VETTED" })]);
}

function consumedVdGreenlit(dir, edId, reg) {
  // An ED is buildable when the VD it consumes is GREENLIT. The VD greenlight
  // transitively authorizes the ED build (the canon executor runs the ED off
  // the VD's GREENLIT line). Returns the greenlit VD line or null.
  const edFile = path.join(dir, "ED", `${edId}.md`);
  if (!fs.existsSync(edFile)) return null;
  const fm = parseFrontmatter(fs.readFileSync(edFile, "utf8"));
  const vdId = fm.consumes;
  if (!vdId || !validId(vdId)) return null;
  const vdPrev = latestLine(reg, vdId);
  if (vdPrev && vdPrev.state === "GREENLIT" && vdPrev.go_basis) return vdPrev;
  return null;
}

function cmdBuilt(args) {
  // built <cwd> <id> <GREEN|RED> [cycles_to_green] [defects]
  const [cwd, id, color, cycles, defects] = args;
  if (!validId(id)) die(2, `bad id: ${id}`);
  if (color !== "GREEN" && color !== "RED") die(2, `bad color: ${color}`);
  const dir = runtimeDir(cwd);
  const reg = readRegistry(dir);
  const prev = latestLine(reg, id);
  // An ED is buildable via its consumed VD's GREENLIT; a VD/packet is buildable
  // via its own GREENLIT. Either path satisfies the executor's greenlight gate.
  const ownGreenlit = prev && prev.state === "GREENLIT";
  const vdGreenlit = kindOf(id) === "ED" ? consumedVdGreenlit(dir, id, reg) : null;
  if (!ownGreenlit && !vdGreenlit) {
    die(2, `cannot build ${id}: latest state is ${prev ? prev.state : "(none)"}, need GREENLIT (own or consumed VD)`);
  }
  const state = color === "GREEN" ? "BUILT-GREEN" : "BUILT-RED";
  const entry = { id, state, smoke_first_run: color === "GREEN" };
  if (cycles) entry.cycles_to_green = Number(cycles);
  if (defects) entry.defects = defects;
  cmdAppend([cwd, JSON.stringify(entry)]);
}

function cmdVerified(args) {
  // verified <cwd> <id>
  const [cwd, id] = args;
  if (!validId(id)) die(2, `bad id: ${id}`);
  const dir = runtimeDir(cwd);
  const reg = readRegistry(dir);
  const prev = latestLine(reg, id);
  if (!prev || prev.state !== "BUILT-GREEN") {
    die(2, `cannot verify ${id}: latest state is ${prev ? prev.state : "(none)"}, need BUILT-GREEN`);
  }
  cmdAppend([cwd, JSON.stringify({ id, state: "VERIFIED" })]);
}

function cmdReopened(args) {
  // reopened <cwd> <id> <reason>
  const [cwd, id, reason] = args;
  if (!validId(id)) die(2, `bad id: ${id}`);
  if (!reason) die(2, "REOPENED requires a non-empty reason");
  cmdAppend([cwd, JSON.stringify({ id, state: "REOPENED", reason })]);
}

// ---------- phase gate (the fail-closed boundary check) ----------

function cmdGate(args) {
  // gate <cwd> <check> [args...]
  const [cwd, check, ...rest] = args;
  const dir = runtimeDir(cwd);
  const cur = readJson(path.join(dir, "cursor.json"), null);
  if (!cur) die(2, `no cursor; run init`);
  const reg = readRegistry(dir);
  let pass = true;
  let bounce = false;
  const reasons = [];

  switch (check) {
    case "cursor-valid": {
      if (!PHASES.includes(cur.phase)) { pass = false; reasons.push("bad phase"); }
      if (!["orchestrator", "author", "coder", "reviewer", "idle"].includes(cur.role)) { pass = false; reasons.push("bad role"); }
      if (cur.active_directive !== null && !validId(cur.active_directive)) { pass = false; reasons.push("bad active_directive"); }
      break;
    }
    case "cursor-not-mid-build": {
      if (cur.role === "coder" && cur.active_directive !== null) {
        pass = false; reasons.push(`build in flight: ${cur.active_directive}`);
      }
      break;
    }
    case "cursor-phase-match": {
      // gate <cwd> cursor-phase-match <phase>
      const target = rest[0];
      if (!PHASES.includes(target)) die(2, `bad target phase: ${target}`);
      // allow source or destination of the boundary
      const allowed = cur.phase === target || cur.phase === "validation" && target === "execution";
      if (!allowed) { pass = false; reasons.push(`cursor phase ${cur.phase} not at ${target} boundary`); }
      break;
    }
    case "ed-latest-greenlit": {
      // gate <cwd> ed-latest-greenlit <id> — kept for back-compat; the honest
      // name for VD-derived authority is vd-latest-greenlit (below). Both check
      // that <id>'s latest registry line is GREENLIT with go_basis.
      const id = rest[0];
      if (!validId(id)) die(2, `bad id: ${id}`);
      const prev = latestLine(reg, id);
      if (!prev || prev.state !== "GREENLIT") {
        pass = false; reasons.push(`${id} latest state is ${prev ? prev.state : "(none)"}, need GREENLIT`);
      }
      if (prev && !prev.go_basis) { pass = false; reasons.push(`${id} GREENLIT without go_basis`); }
      break;
    }
    case "vd-latest-greenlit": {
      // gate <cwd> vd-latest-greenlit <vd-id> — the honest name for the
      // authority check that authorizes an ED build (the ED consumes a
      // GREENLIT VD). Use this from the extension; ed-latest-greenlit is the
      // legacy alias.
      const id = rest[0];
      if (!validId(id)) die(2, `bad id: ${id}`);
      const prev = latestLine(reg, id);
      if (!prev || prev.state !== "GREENLIT") {
        pass = false; reasons.push(`${id} latest state is ${prev ? prev.state : "(none)"}, need GREENLIT`);
      }
      if (prev && !prev.go_basis) { pass = false; reasons.push(`${id} GREENLIT without go_basis`); }
      break;
    }
    case "lane-still-disjoint": {
      // gate <cwd> lane-still-disjoint <lane-name> — re-check at execute time
      // that the lane's declared files are still disjoint from every OTHER
      // in-flight lane. Closes the register→execute TOCTOU (F2): a lane
      // registered disjoint can be overlapped by a later lane before the
      // coder starts writing.
      const lane = rest[0];
      const laneFile = path.join(dir, "lanes", lane + ".json");
      if (!fs.existsSync(laneFile)) { pass = false; reasons.push(`lane ${lane} not registered`); break; }
      const mine = (readJson(laneFile, { files: [] })).files || [];
      const lanesDir = path.join(dir, "lanes");
      for (const name of fs.readdirSync(lanesDir)) {
        if (name === lane + ".json") continue;
        const other = (readJson(path.join(lanesDir, name), { files: [] })).files || [];
        const overlap = mine.filter((f) => other.includes(f));
        if (overlap.length) { pass = false; reasons.push(`lane ${name} overlaps ${lane} on ${overlap.join(", ")}`); }
      }
      break;
    }
    case "ed-chain-walkback": {
      // gate <cwd> ed-chain-walkback <ed-file>
      const edFile = rest[0];
      if (!fs.existsSync(edFile)) die(2, `ed file missing: ${edFile}`);
      const text = fs.readFileSync(edFile, "utf8");
      const fm = parseFrontmatter(text);
      const format = fm.format || "v1";
      if (format === "v1") { break; } // forward gate, never retro
      if (format !== "v2") { pass = false; reasons.push(`bad format: ${format}`); break; }
      const cw = fm["chain-walkback"];
      if (!cw || !cw.trim()) { pass = false; reasons.push("format v2 requires non-empty chain-walkback"); break; }
      // shape: -> separated segments, each a comma-list of (VD|DD|PD)-NNN refs
      const segs = cw.split("->").map((s) => s.trim());
      if (segs.some((s) => !s)) { pass = false; reasons.push("malformed chain (empty segment)"); break; }
      for (const seg of segs) {
        const refs = seg.split(",").map((r) => r.trim());
        for (const r of refs) {
          if (!/^(VD|DD|PD)-\d{3}$/.test(r)) { pass = false; reasons.push(`bad chain ref: ${r}`); }
        }
      }
      break;
    }
    case "pd-dd-pairing": {
      // gate <cwd> pd-dd-pairing — every DD has a paired PD
      const ddDir = path.join(dir, "DD");
      const pdDir = path.join(dir, "PD");
      if (!fs.existsSync(ddDir)) break;
      for (const name of fs.readdirSync(ddDir)) {
        if (!name.endsWith(".md")) continue;
        const m = ID_RE.exec(name.replace(/\.md$/, ""));
        if (!m) continue;
        const pd = path.join(pdDir, `PD-${m[2]}.md`);
        if (!fs.existsSync(pd)) { pass = false; reasons.push(`DD-${m[2]} has no paired PD`); }
      }
      break;
    }
    case "dd-status-settled": {
      // gate <cwd> dd-status-settled <dd-file>
      const ddFile = rest[0];
      if (!fs.existsSync(ddFile)) die(2, `dd file missing: ${ddFile}`);
      const fm = parseFrontmatter(fs.readFileSync(ddFile, "utf8"));
      if (fm.status !== "settled") { pass = false; reasons.push(`dd status is ${fm.status || "(none)"}, need settled`); }
      break;
    }
    case "lane-disjoint": {
      // gate <cwd> lane-disjoint <lane-name> <files-json>
      const lane = rest[0];
      const filesJson = rest[1];
      let files;
      try { files = JSON.parse(filesJson); } catch { die(2, "bad files json"); }
      if (!Array.isArray(files)) die(2, "files must be an array");
      const lanesDir = path.join(dir, "lanes");
      ensureDir(lanesDir);
      // check overlap against all in-flight lanes (not this one)
      for (const name of fs.readdirSync(lanesDir)) {
        if (name === lane + ".json") continue;
        const other = readJson(path.join(lanesDir, name), { files: [] });
        const overlap = files.filter((f) => other.files.includes(f));
        if (overlap.length) {
          pass = false; reasons.push(`lane ${name} overlaps on ${overlap.join(", ")}`);
        }
      }
      // also check disjointness WITHIN the lane (provably disjoint sub-packages)
      const seen = new Map();
      for (const f of files) {
        if (seen.has(f)) { pass = false; reasons.push(`duplicate file in lane: ${f}`); }
        seen.set(f, true);
      }
      break;
    }
    case "lane-register": {
      // gate <cwd> lane-register <lane-name> <files-json>
      const lane = rest[0];
      const filesJson = rest[1];
      let files;
      try { files = JSON.parse(filesJson); } catch { die(2, "bad files json"); }
      const lanesDir = path.join(dir, "lanes");
      ensureDir(lanesDir);
      atomicWrite(path.join(lanesDir, lane + ".json"), JSON.stringify({ files, ts: now() }, null, 2) + "\n");
      break;
    }
    case "lane-release": {
      // gate <cwd> lane-release <lane-name>
      const lane = rest[0];
      const f = path.join(dir, "lanes", lane + ".json");
      if (fs.existsSync(f)) fs.rmSync(f);
      break;
    }
    default:
      die(2, `unknown check: ${check}`);
  }

  if (!pass) {
    // BOUNCE (exit 1) for soft fails; BLOCK (exit 2) for hard fails.
    // We treat all our checks as hard (fail-closed) — the framework's
    // execution-intake is strict-hard. Use exit 2.
    die(2, `BLOCK: ${check} -> ${reasons.join("; ")}`);
  }
  process.stdout.write(`PASS: ${check}\n`);
}

function parseFrontmatter(text) {
  const m = /^---\n([\s\S]*?)\n---/.exec(text);
  if (!m) return {};
  const out = {};
  for (const line of m[1].split("\n")) {
    const i = line.indexOf(":");
    if (i < 0) continue;
    const k = line.slice(0, i).trim();
    const v = line.slice(i + 1).trim();
    out[k] = v;
  }
  return out;
}

// ---------- packet allocation + authoring ----------

function cmdAlloc(args) {
  // alloc <cwd> <kind> [count]
  const [cwd, kind, countRaw] = args;
  if (!PACKET_KINDS.has(kind)) die(2, `bad kind: ${kind}`);
  const dir = runtimeDir(cwd);
  const kindDir = path.join(dir, kind);
  ensureDir(kindDir);
  const dirs = [...PACKET_KINDS].map((k) => path.join(dir, k));
  const start = nextSerial(dirs);
  const count = Math.max(1, Number(countRaw) || 1);
  const ids = [];
  for (let i = 0; i < count; i++) {
    const n = pad3(start + i);
    const id = `${kind}-${n}`;
    const file = path.join(kindDir, `${id}.md`);
    if (fs.existsSync(file)) die(2, `collision: ${file} exists`);
    const template = packetTemplate(id, kind);
    fs.writeFileSync(file, template);
    ids.push(id);
  }
  process.stdout.write(JSON.stringify(ids) + "\n");
}

function packetTemplate(id, kind) {
  const pair = (kind === "PD" || kind === "DD") ? `\npair: ${kind === "PD" ? "DD" : "PD"}-${id.slice(-3)}` : "";
  const fm = [
    "---",
    `id: ${id}`,
    `kind: ${kind}`,
    `status: draft`,
    kind === "ED" ? `format: v2` : null,
    kind === "ED" ? `chain-walkback: VD-NNN -> DD-NNN -> PD-NNN` : null,
    pair.trim() ? pair.trim() : null,
    `author: `,
    `created: ${now()}`,
    "---",
    "",
    `# ${id} — ${kind} packet`,
    "",
  ].filter(Boolean).join("\n");
  return fm + "\n";
}

function cmdHelp() {
  process.stdout.write(`directives-runtime.mjs — native directive pipeline substrate for pi
Usage: node directives-runtime.mjs <command> [args...]
Commands:
  init <cwd>                      create runtime dir + cursor + packet dirs (idempotent)
  dir <cwd>                       print runtime dir
  cursor <cwd>                    print + validate cursor
  set-cursor <cwd> <phase> <role> <active|-> [boundary] [lane]
  postpone <cwd>                  increment postpone budget (max 2)
  registry <cwd> [id]             print registry (or latest line for id)
  append <cwd> <json>             append a registry line (validated)
  vetted <cwd> <id>               mark id VETTED
  greenlight <cwd> <id> <go_basis> mark id GREENLIT (requires VETTED)
  built <cwd> <id> <GREEN|RED> [cycles] [defects]
  verified <cwd> <id>            mark id VERIFIED
  reopened <cwd> <id> <reason>   mark id REOPENED
  alloc <cwd> <kind> [count]     allocate next packet id(s); writes template stub
  gate <cwd> <check> [args...]   run a phase-gate check (0 PASS / 2 BLOCK)
Gate checks:
  cursor-valid
  cursor-not-mid-build
  cursor-phase-match <phase>
  ed-latest-greenlit <id>      (legacy alias; checks <id> latest GREENLIT)
  vd-latest-greenlit <vd-id>   (honest name for ED-build authority)
  ed-chain-walkback <ed-file>
  pd-dd-pairing
  dd-status-settled <dd-file>
  lane-disjoint <lane> <files-json>      (checked at register time)
  lane-still-disjoint <lane>             (re-checked at execute time; closes TOCTOU)
  lane-register <lane> <files-json>
  lane-release <lane>
Exit codes: 0 OK / 2 BLOCK (fail-closed). No soft bounce in this native fusion.
`);
}

// ---------- dispatch ----------

const [cmd, ...rest] = process.argv.slice(2);

// async wrapper for append's lock wait
async function main() {
  switch (cmd) {
    case "init": return cmdInit(rest);
    case "dir": return cmdDir(rest);
    case "cursor": return cmdCursor(rest);
    case "set-cursor": return cmdSetCursor(rest);
    case "postpone": return cmdPostpone(rest);
    case "registry": return cmdRegistry(rest);
    case "append": return await cmdAppend(rest);
    case "vetted": return cmdVetted(rest);
    case "greenlight": return cmdGreenlight(rest);
    case "built": return cmdBuilt(rest);
    case "verified": return cmdVerified(rest);
    case "reopened": return cmdReopened(rest);
    case "alloc": return cmdAlloc(rest);
    case "gate": return cmdGate(rest);
    case "help": case "--help": case "-h": case undefined: return cmdHelp();
    default: die(2, `unknown command: ${cmd}\nrun: node directives-runtime.mjs help`);
  }
}

main().catch((e) => die(2, `fatal: ${e.message}`));
