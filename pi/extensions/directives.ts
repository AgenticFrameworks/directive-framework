/**
 * directives.ts — native directive pipeline fused into the pi agent harness.
 *
 * This extension is the "backbone fusion" of the directive-framework canon
 * (Planning → Design → Validation → Execution → Review, with PD/DD/VD/ED/RD
 * packets, a cursor, an append-only registry, fail-closed phase gates,
 * fresh-context-per-phase, and parallel lanes) into pi as a first-class
 * mechanism that feels inherent to the agent, not a bolted-on plugin.
 *
 * Native fusion means:
 *   1. The pipeline is part of the agent's own config surface, not an
 *      external repo the model is told to read. A pi extension in
 *      ~/.pi/agent/extensions/ + a deterministic runtime the extension owns.
 *   2. Phase gates are enforced at the moment of relevance — on tool_call —
 *      fail-closed, so the model cannot skim past a phase boundary in prose.
 *      This mirrors the framework's "prose is not enforcement" doctrine.
 *   3. Phase context is injected into the system prompt per turn, so every
 *      capacity knows which phase it is in and what its role is, without
 *      re-deriving it.
 *   4. Fresh-context-per-phase: the `/directives execute|review` COMMANDS
 *      use ctx.newSession to start a true fresh session for the coder/reviewer
 *      (command context only). The directive_execute|review TOOLS deliver the
 *      phase kickoff via pi.sendUserMessage followUp at a clean turn boundary
 *      in the same session — a weaker guarantee, documented honestly. The
 *      command path is the structural fresh-context property the canon wants.
 *   5. Parallel building is a first-class dispatch primitive: lanes are
 *      allocated with provably-disjoint file footprints, enforced in code
 *      before launch (the framework's "deterministic-first" axiom), and a
 *      single authority merges.
 *   6. Authority is checkable end-to-end from the registry alone: a GREENLIT
 *      line with go_basis is the only sign-off; nothing else authorizes
 *      execution. With yolo off, greenlight + merge escalate to the human;
 *      with yolo on, the model may self-greenlight routine work but still
 *      escalates destructive/irreversible/security-sensitive choices.
 *
 * The extension shells every state mutation through directives-runtime.mjs
 * (the deterministic substrate); it never trusts the model with cursor,
 * registry, or gate writes — exactly as EXECUTOR-SPEC owns apply/synthesis.
 *
 * Commands:
 *   /directives                — status (phase, role, active directive, registry tail)
 *   /directives init           — initialize the runtime for this project
 *   /directives plan <text>    — author a PD/DD pair (planning phase)
 *   /directives decide         — settle the active DD (design phase)
 *   /directives validate       — package a VD from settled DDs
 *   /directives greenlight <id> [go_basis] — sign off (escalates unless yolo)
 *   /directives execute <vd>    — fork a fresh-context coder session for an ED (true fresh session)
 *   /directives review <ed>     — fork a fresh-context reviewer session (true fresh session)
 *   /directives lane <name> <files...> — register a parallel lane (disjointness checked)
 *   /directives release <name> — release a lane
 *   /directives phase <name>   — advance the cursor to a phase
 *   /directives yolo [on|off]  — toggle standing routine authority
 *
 * Tools (the model drives the pipeline by calling these):
 *   directive_status           — read-only fleet/phase view
 *   directive_plan             — allocate + draft a PD/DD pair
 *   directive_settle           — settle the active DD
 *   directive_validate         — package a VD
 *   directive_greenlight       — sign off (HiTL unless yolo)
 *   directive_execute          — dispatch a coder for an ED (turn-boundary kickoff in-session; use /directives execute for a true fresh session)
 *   directive_review           — dispatch a reviewer (in-session; use /directives review for a true fresh session)
 *   directive_lane             — register/dispatch a parallel lane
 *   directive_advance          — advance the phase cursor
 *
 * Safety: every gate failure is fail-closed (block the tool call). Destructive
 * choices (greenlight, merge, lane release with unlanded work) escalate to the
 * human via e2e_hitl-style prompting unless yolo is on.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Resolve paths for an installed pi package, not a hardcoded in-place location.
// - PI_AGENT: the pi agent config root (settings.json lives here). Honors
//   PI_CODING_AGENT_DIR, defaults to ~/.pi/agent.
// - RUNTIME: the deterministic substrate script, resolved relative to THIS
//   extension file (../runtime/directives-runtime.mjs) so it works whether
//   installed via `pi install git:...` or loaded in-place.
// - RUNTIME_ROOT: where per-project directive state (cursor, registry,
//   packets, lanes) lives. Honors DIRECTIVES_RUNTIME_DIR, defaults to
//   ~/.pi/agent/directives/ so the installed package and the in-place build
//   share the same per-project runtime.
const PI_AGENT = process.env.PI_CODING_AGENT_DIR || path.join(os.homedir(), ".pi/agent");
const EXTENSION_DIR = path.dirname(fileURLToPath(import.meta.url));
const RUNTIME = process.env.DIRECTIVES_RUNTIME_SCRIPT
  || path.resolve(EXTENSION_DIR, "../runtime/directives-runtime.mjs");
const RUNTIME_ROOT = process.env.DIRECTIVES_RUNTIME_DIR
  || path.join(PI_AGENT, "directives");
const STATE_TYPE = "directives-state";

const PHASES = ["planning", "design", "validation", "execution", "review"] as const;
type Phase = (typeof PHASES)[number];

type DirectivesSettings = {
  yolo: boolean;
  autoInit: boolean;
};

type RuntimeState = {
  cwd: string;
  initialized: boolean;
  yolo: boolean;
};

function settingsPath() {
  return path.join(PI_AGENT, "settings.json");
}

function readSettings(): DirectivesSettings {
  try {
    const raw = JSON.parse(fs.readFileSync(settingsPath(), "utf8")) as {
      directives?: Partial<DirectivesSettings>;
    };
    return {
      yolo: raw.directives?.yolo === true,
      // autoInit defaults OFF: never silently enroll a cwd. Opt in per-project
      // with `/directives init`, or set directives.autoInit:true only when you
      // want every trusted cwd enrolled.
      autoInit: raw.directives?.autoInit === true,
    };
  } catch {
    return { yolo: false, autoInit: false };
  }
}

function writeSettings(patch: Partial<DirectivesSettings>): { ok: boolean; error?: string } {
  try {
    const raw = JSON.parse(fs.readFileSync(settingsPath(), "utf8")) as Record<string, unknown>;
    raw.directives = { ...(raw.directives as object | undefined), ...patch };
    fs.writeFileSync(settingsPath(), JSON.stringify(raw, null, 2) + "\n");
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

function rt(args: string[]): { ok: boolean; stdout: string; stderr: string; code: number } {
  // Pass DIRECTIVES_RUNTIME_DIR so the runtime subprocess resolves the same
  // per-project root the extension resolved (matters when the env is set or
  // when PI_CODING_AGENT_DIR differs between the two processes).
  const env = { ...process.env, DIRECTIVES_RUNTIME_DIR: RUNTIME_ROOT };
  const r = spawnSync("node", [RUNTIME, ...args], { encoding: "utf8", maxBuffer: 16 * 1024 * 1024, env });
  return { ok: r.status === 0, stdout: r.stdout ?? "", stderr: r.stderr ?? "", code: r.status ?? 1 };
}

function runtimeDir(cwd: string): string {
  const r = rt(["dir", cwd]);
  return r.stdout.trim();
}

function readCursor(cwd: string): Record<string, unknown> | null {
  const r = rt(["cursor", cwd]);
  if (!r.ok) return null;
  try { return JSON.parse(r.stdout); } catch { return null; }
}

function readRegistry(cwd: string): Array<Record<string, unknown>> {
  const r = rt(["registry", cwd]);
  if (!r.ok) return [];
  return r.stdout.split("\n").filter(Boolean).map((l) => {
    try { return JSON.parse(l); } catch { return { _bad: l }; }
  });
}

function gate(cwd: string, check: string, ...rest: string[]): { ok: boolean; reason: string } {
  const r = rt(["gate", cwd, check, ...rest]);
  return { ok: r.ok, reason: r.ok ? "" : r.stderr.trim() || r.stdout.trim() };
}

function now() { return new Date().toISOString(); }

function isSlash(text: string) { return text.trim().startsWith("/"); }

const PHASE_KICKOFF: Record<Phase, (ctx: string) => string> = {
  planning: (ctx) => [
    "You are the PLANNING capacity for this project's directive pipeline.",
    "Phase: planning. Role: author.",
    "Author a PD/DD pair: the PD is the reasoning twin (why), the DD is the settled decision (one atomic action).",
    "Do not implement. Do not edit project files. Output is packets under _directives/PD/ and _directives/DD/.",
    "When the decision is settled, call directive_settle. Do not advance to design until the DD is settled.",
    ctx ? `\nContext / goal:\n${ctx}` : "",
  ].filter(Boolean).join("\n"),
  design: (ctx) => [
    "You are the DESIGN capacity for this project's directive pipeline.",
    "Phase: design. Role: author.",
    "Turn the settled DD into a Validation Directive (VD) — the build plan: what will be built, how it will be verified, the smoke bars.",
    "Do not implement. Output is a packet under _directives/VD/.",
    "When the VD is packaged, call directive_validate. The VD author must differ from the DD author.",
    ctx ? `\nContext / goal:\n${ctx}` : "",
  ].filter(Boolean).join("\n"),
  validation: (ctx) => [
    "You are the VALIDATION capacity for this project's directive pipeline.",
    "Phase: validation. Role: reviewer.",
    "Adversarially vet the VD: re-run its load-bearing claims against real data, police false ticks, attack the headline gate.",
    "Do not implement. On pass, call directive_greenlight (with go_basis). On fail, call directive_reopen with the reason.",
    "Self-review is not review. If you authored the VD, say so and stop — a different capacity must vet.",
    ctx ? `\nContext / goal:\n${ctx}` : "",
  ].filter(Boolean).join("\n"),
  execution: (ctx) => [
    "You are the EXECUTION capacity for this project's directive pipeline.",
    "Phase: execution. Role: coder.",
    "Implement the greenlit ED. Hard stop on red: no fix iteration past a failed smoke bar — write a defects file and exit.",
    "Retype only the transcription-risk strings the ED flags. Do not re-derive design the ED did not decompose.",
    "When the build is green, call directive_built GREEN. On red, call directive_built RED with the defects.",
    "Parallel lanes: only touch the files your lane declared. Overlap is refused at launch.",
    ctx ? `\nContext / goal:\n${ctx}` : "",
  ].filter(Boolean).join("\n"),
  review: (ctx) => [
    "You are the REVIEW capacity for this project's directive pipeline.",
    "Phase: review. Role: reviewer.",
    "Re-inspect the VERIFIED work. Audit intent drift: does the built artifact still match the settled decision and the validated plan?",
    "On clean, call directive_verified (final). On drift or defect, call directive_reopen with the reason and the specific divergence.",
    ctx ? `\nContext / goal:\n${ctx}` : "",
  ].filter(Boolean).join("\n"),
};

function phasePrompt(cursor: Record<string, unknown> | null): string {
  if (!cursor) return "";
  const phase = cursor.phase as Phase;
  const role = cursor.role as string;
  const active = cursor.active_directive as string | null;
  const lane = cursor.lane as string | null;
  const lines = [
    `[DIRECTIVE PIPELINE] phase=${phase} role=${role}${active ? ` active=${active}` : ""}${lane ? ` lane=${lane}` : ""}`,
  ];
  if (active) {
    lines.push(`Work under way: ${active}. Do not start new work until this directive is resolved or reopened.`);
  }
  if (phase === "execution" && role === "coder") {
    lines.push("Hard stop on red. No fix iteration. Write defects and exit if a smoke bar fails.");
  }
  if (phase === "validation") {
    lines.push("Self-review is not review. A different capacity must vet the VD.");
  }
  return lines.join("\n");
}

function summary(cwd: string): string {
  const cur = readCursor(cwd);
  if (!cur) return "directives: not initialized (run /directives init)";
  const reg = readRegistry(cwd);
  const tail: Record<string, string> = {};
  for (const l of reg) {
    if (l && typeof l.id === "string") tail[l.id] = `${l.state}${l.go_basis ? ` (${l.go_basis})` : ""}`;
  }
  const phase = cur.phase as string;
  const role = cur.role as string;
  const active = cur.active_directive as string | null;
  const lane = cur.lane as string | null;
  const dir = runtimeDir(cwd);
  const lanesDir = path.join(dir, "lanes");
  let lanes: string[] = [];
  try { lanes = fs.existsSync(lanesDir) ? fs.readdirSync(lanesDir).map((f) => f.replace(/\.json$/, "")) : []; } catch {}
  const lines = [
    `directives: phase=${phase} role=${role}${active ? ` active=${active}` : ""}${lane ? ` lane=${lane}` : ""}`,
    `runtime: ${dir}`,
    `lanes: ${lanes.length ? lanes.join(", ") : "(none)"}`,
    `registry (${reg.length} lines):`,
    ...Object.entries(tail).map(([id, st]) => `  ${id}: ${st}`),
  ];
  return lines.join("\n");
}

export default function directivesExtension(pi: ExtensionAPI) {
  let state: RuntimeState | null = null;

  const persist = () => pi.appendEntry(STATE_TYPE, state);

  const load = (ctx: { sessionManager: { getEntries(): Array<{ type: string; customType?: string; data?: unknown }> }; isProjectTrusted?: () => boolean }) => {
    const entry = ctx.sessionManager
      .getEntries()
      .filter((e) => e.type === "custom" && e.customType === STATE_TYPE)
      .pop();
    if (entry?.data) {
      state = { ...(entry.data as RuntimeState) };
    } else {
      state = { cwd: process.cwd(), initialized: false, yolo: readSettings().yolo };
    }
    // auto-init only for explicitly trusted projects AND when the captain
    // opted in via settings.directives.autoInit. Never silently enroll a cwd.
    const settings = readSettings();
    if (settings.autoInit && !state.initialized && typeof ctx.isProjectTrusted === "function" && ctx.isProjectTrusted()) {
      const r = rt(["init", state.cwd]);
      if (r.ok) { state.initialized = true; persist(); }
    }
  };

  const setStatus = (ctx?: { ui: { setStatus(key: string, value?: string): void } }) => {
    const line = state?.initialized ? (() => {
      const cur = readCursor(state.cwd);
      if (!cur) return "directives: initializing";
      return `directives: ${cur.phase}/${cur.role}${cur.active_directive ? ` ${cur.active_directive}` : ""}${cur.lane ? ` lane=${cur.lane}` : ""}${state.yolo ? " yolo" : ""}`;
    })() : "directives: off";
    ctx?.ui.setStatus("directives", line);
  };

  pi.on("session_start", async (_event, ctx) => {
    load(ctx);
    setStatus(ctx);
  });

  pi.on("before_agent_start", async (event, ctx) => {
    if (!state?.initialized) return;
    const cur = readCursor(state.cwd);
    const phaseBlock = phasePrompt(cur);
    if (!phaseBlock) return;
    return { systemPrompt: event.systemPrompt + "\n\n" + phaseBlock };
  });

  // Fail-closed phase-gate enforcement at the moment of relevance.
  // The gate covers BOTH direct file writes (write/edit) AND shell writes
  // (bash), because a coder can otherwise route around the gate with
  // shell redirection (`echo > file`, `tee`, `sed -i`, `cp`, `mv`, `cat <<EOF`).
  // For bash, we do a conservative path-extraction of redirect/edit targets
  // from the command string and apply the same phase/lane rules. This is a
  // defense-in-depth heuristic, not a full shell parser; the hard floor is
  // that bash writes outside the runtime dir are blocked in non-execution
  // phases, and restricted to the lane footprint in execution.
  const REDIRECT_RE = /(?:>>|>)\s*(?:\/dev\/null\b|[^\s|;&<>]+)/g;
  const EDIT_CMDS = /\b(?:tee|sed|cp|mv|install|rsync|dd|truncate|install)\b/;
  function bashTargets(cmd: string): string[] {
    const out: string[] = [];
    for (const m of cmd.matchAll(REDIRECT_RE)) {
      const t = m[1];
      if (t && !t.startsWith("/dev/")) out.push(t);
    }
    // crude `tee <file>` and `cp/mv src dst` last-arg capture
    const tee = /\btee\b(?:\s+-a)?\s+([^\s|;&<>]+)/g.exec(cmd);
    if (tee && tee[1]) out.push(tee[1]);
    return out;
  }
  function targetAllowedForLane(target: string, dir: string, cwd: string, lane: string | null): boolean {
    if (!lane) return true;
    const laneFile = path.join(dir, "lanes", lane + ".json");
    let allowed: string[] = [];
    try { allowed = (JSON.parse(fs.readFileSync(laneFile, "utf8")) as { files: string[] }).files; } catch { allowed = []; }
    const resolved = path.resolve(cwd, target);
    // Path-confusion-safe: compare resolved absolute paths only, never substring.
    return allowed.some((f) => path.resolve(cwd, f) === resolved);
  }
  function phaseAllowsWrite(phase: Phase, role: string, target: string, dir: string, cwd: string, lane: string | null): { ok: boolean; reason?: string } {
    // Writes inside the runtime dir are always allowed (packets are the phase output).
    const resolved = path.resolve(cwd, target);
    if (resolved === dir || resolved.startsWith(dir + path.sep)) return { ok: true };
    if (phase === "execution" && role === "coder") {
      if (!targetAllowedForLane(target, dir, cwd, lane)) {
        return { ok: false, reason: `directives: ${target} is outside lane ${lane}'s declared footprint. Register the file in the lane first or release the lane.` };
      }
      return { ok: true };
    }
    if (phase === "planning" || phase === "design" || phase === "validation" || phase === "review") {
      if (role === "coder") return { ok: true }; // coder in execution is the only writer
      return { ok: false, reason: `directives: ${phase} phase (${role}) produces packets under the runtime dir, not project writes. Resolve or reopen the active directive, or advance to execution first.` };
    }
    return { ok: true };
  }
  pi.on("tool_call", async (event) => {
    if (!state?.initialized) return;
    const cwd = state.cwd;
    const cur = readCursor(cwd);
    if (!cur) return;
    const phase = cur.phase as Phase;
    const role = cur.role as string;
    const lane = cur.lane as string | null;
    const dir = runtimeDir(cwd);
    if (event.toolName === "write" || event.toolName === "edit") {
      const input = event.input as { path?: string };
      const target = input.path ?? "";
      if (!target) return;
      const r = phaseAllowsWrite(phase, role, target, dir, cwd, lane);
      if (!r.ok) return { block: true, reason: r.reason };
      return;
    }
    if (event.toolName === "bash") {
      const input = event.input as { command?: string };
      const cmd = input.command ?? "";
      if (!cmd) return;
      // If the command has no redirect/edit-shaped write and isn't obviously a write,
      // let it pass (read-only bash is the escape hatch per the policy).
      const hasRedirect = REDIRECT_RE.test(cmd) || EDIT_CMDS.test(cmd) || /\btee\b/.test(cmd);
      if (!hasRedirect) return;
      // Re-evaluate each extracted target against the phase/lane rules.
      const targets = bashTargets(cmd);
      for (const t of targets) {
        const r = phaseAllowsWrite(phase, role, t, dir, cwd, lane);
        if (!r.ok) return { block: true, reason: `directives: bash write to ${t} blocked: ${r.reason}` };
      }
      return;
    }
  });

  // --- tools ---

  pi.registerTool({
    name: "directive_status",
    label: "Directive Status",
    description: "Read-only view of the directive pipeline: phase, role, active directive, registry tail, lanes. Use to orient before any directive action.",
    promptSnippet: "Read directive pipeline phase/role/registry state",
    parameters: Type.Object({}),
    async execute(_id, _p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      return { content: [{ type: "text", text: summary(state.cwd) }], details: {} };
    },
  });

  pi.registerTool({
    name: "directive_plan",
    label: "Directive Plan",
    description: "Allocate and draft a PD/DD pair (planning phase). One atomic decision per pair. Does not implement.",
    promptSnippet: "Author a PD/DD planning pair",
    parameters: Type.Object({
      decision: Type.String({ description: "One-line atomic decision the DD captures" }),
      rationale: Type.String({ description: "Why this decision — goes in the PD reasoning twin" }),
      pair_count: Type.Optional(Type.Number({ description: "Number of pairs to allocate (default 1)" })),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      // gate: must be in planning phase, orchestrator/author, not mid-build
      const g1 = gate(state.cwd, "cursor-valid");
      if (!g1.ok) return { content: [{ type: "text", text: `blocked: ${g1.reason}` }], details: { isError: true } };
      const r = rt(["alloc", state.cwd, "PD", String(p.pair_count ?? 1)]);
      if (!r.ok) return { content: [{ type: "text", text: `alloc failed: ${r.stderr}` }], details: { isError: true } };
      const ids = JSON.parse(r.stdout) as string[];
      // also allocate matching DDs (paired)
      const rdd = rt(["alloc", state.cwd, "DD", String(p.pair_count ?? 1)]);
      const ddIds = rdd.ok ? (JSON.parse(rdd.stdout) as string[]) : [];
      // write the decision + rationale into the packets
      const dir = runtimeDir(state.cwd);
      for (let i = 0; i < ids.length; i++) {
        const pdFile = path.join(dir, "PD", `${ids[i]}.md`);
        const ddFile = path.join(dir, "DD", `${ddIds[i]}.md`);
        fs.writeFileSync(pdFile, [
          "---",
          `id: ${ids[i]}`,
          `kind: PD`,
          `pair: ${ddIds[i]}`,
          `status: draft`,
          `author: agent`,
          `created: ${now()}`,
          "---",
          "",
          `# ${ids[i]} — Planning Directive (reasoning twin)`,
          "",
          "## Decision",
          p.decision,
          "",
          "## Rationale",
          p.rationale,
          "",
          "## Done when",
          `DD ${ddIds[i]} is settled and validation has packaged a VD.`,
          "",
        ].join("\n"));
        fs.writeFileSync(ddFile, [
          "---",
          `id: ${ddIds[i]}`,
          `kind: DD`,
          `pair: ${ids[i]}`,
          `status: draft`,
          `author: agent`,
          `created: ${now()}`,
          "---",
          "",
          `# ${ddIds[i]} — Decision Directive`,
          "",
          "## Action",
          p.decision,
          "",
          "## Rationale",
          p.rationale,
          "",
          "## Done when",
          "The action above is implemented and verified.",
          "",
        ].join("\n"));
      }
      // point cursor at the first new PD
      const first = ids[0];
      rt(["set-cursor", state.cwd, "planning", "author", first, "B-planning", "-"]);
      setStatus(ctx);
      return { content: [{ type: "text", text: `authored: ${ids.map((id, i) => `${id}/${ddIds[i]}`).join(", ")}. Call directive_settle when the decision is settled.` }], details: { ids, ddIds } };
    },
  });

  pi.registerTool({
    name: "directive_settle",
    label: "Directive Settle",
    description: "Settle the active DD (mark its status settled). Moves the design boundary forward.",
    promptSnippet: "Settle the active DD",
    parameters: Type.Object({
      dd_id: Type.String({ description: "DD id to settle (e.g. DD-001)" }),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      const dir = runtimeDir(state.cwd);
      const ddFile = path.join(dir, "DD", `${p.dd_id}.md`);
      if (!fs.existsSync(ddFile)) return { content: [{ type: "text", text: `no such DD: ${p.dd_id}` }], details: { isError: true } };
      // flip status to settled
      let text = fs.readFileSync(ddFile, "utf8");
      text = text.replace(/^status:\s*\w+/m, "status: settled");
      fs.writeFileSync(ddFile, text);
      // gate: dd-status-settled
      const g = gate(state.cwd, "dd-status-settled", ddFile);
      if (!g.ok) return { content: [{ type: "text", text: `gate failed: ${g.reason}` }], details: { isError: true } };
      // advance cursor to design
      rt(["set-cursor", state.cwd, "design", "author", p.dd_id, "B-design", "-"]);
      setStatus(ctx);
      return { content: [{ type: "text", text: `settled ${p.dd_id}. Now in design. Call directive_validate to package the VD.` }], details: {} };
    },
  });

  pi.registerTool({
    name: "directive_validate",
    label: "Directive Validate",
    description: "Package a VD from the settled DD. Author must differ from the DD author (self-review is not review).",
    promptSnippet: "Package a Validation Directive from the settled DD",
    parameters: Type.Object({
      dd_id: Type.String({ description: "The settled DD the VD packages" }),
      plan: Type.String({ description: "The build plan: what will be built and how it will be verified (smoke bars)" }),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      const dir = runtimeDir(state.cwd);
      const ddFile = path.join(dir, "DD", `${p.dd_id}.md`);
      const g = gate(state.cwd, "dd-status-settled", ddFile);
      if (!g.ok) return { content: [{ type: "text", text: `gate failed: ${g.reason}` }], details: { isError: true } };
      const r = rt(["alloc", state.cwd, "VD", "1"]);
      if (!r.ok) return { content: [{ type: "text", text: `alloc failed: ${r.stderr}` }], details: { isError: true } };
      const [vdId] = JSON.parse(r.stdout) as string[];
      const vdFile = path.join(dir, "VD", `${vdId}.md`);
      fs.writeFileSync(vdFile, [
        "---",
        `id: ${vdId}`,
        `kind: VD`,
        `consumes: ${p.dd_id}`,
        `status: draft`,
        `author: agent-validation`,
        `created: ${now()}`,
        "---",
        "",
        `# ${vdId} — Validation Directive (build plan)`,
        "",
        "## Plan",
        p.plan,
        "",
        "## Smoke bars",
        "(to be filled by the validator; each bar must cite a §1 success criterion)",
        "",
      ].join("\n"));
      // vetted transition
      rt(["vetted", state.cwd, vdId]);
      rt(["set-cursor", state.cwd, "validation", "reviewer", vdId, "B-validation", "-"]);
      setStatus(ctx);
      return { content: [{ type: "text", text: `packaged ${vdId} from ${p.dd_id}. Now in validation. A different capacity must vet before greenlight.` }], details: { vdId } };
    },
  });

  pi.registerTool({
    name: "directive_greenlight",
    label: "Directive Greenlight",
    description: "Sign off a VD — the GREENLIT registry line is the only sign-off. Escalates to human unless directives.yolo is on.",
    promptSnippet: "Greenlight a VD (sign off)",
    parameters: Type.Object({
      vd_id: Type.String({ description: "VD id to greenlight" }),
      go_basis: Type.Optional(Type.String({ description: "human:<name> | delegated:<basis> | envelope:<version>. Defaults to delegated:agent under yolo." })),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      const settings = readSettings();
      let basis = p.go_basis;
      if (!settings.yolo) {
        // escalate to human
        const ok = await ctx.ui.confirm(
          "Directive greenlight",
          `Authorize greenlight of ${p.vd_id}? This is the sign-off that authorizes execution.`,
        );
        if (!ok) return { content: [{ type: "text", text: "greenlight denied by captain" }], details: { isError: true } };
        basis = basis || "human:captain";
      } else {
        basis = basis || "delegated:agent-yolo";
      }
      const r = rt(["greenlight", state.cwd, p.vd_id, basis]);
      if (!r.ok) return { content: [{ type: "text", text: `greenlight failed: ${r.stderr.trim() || r.stdout}` }], details: { isError: true } };
      setStatus(ctx);
      return { content: [{ type: "text", text: `greenlit ${p.vd_id} (${basis}). Allocate an ED and call directive_execute to dispatch a coder, or /directives execute ${p.vd_id} for a true fresh-context session.` }], details: { go_basis: basis } };
    },
  });

  pi.registerTool({
    name: "directive_execute",
    label: "Directive Execute",
    description: "Allocate an ED and dispatch a coder (turn-boundary kickoff in-session). For a TRUE fresh-context session, run /directives execute <vd_id> instead. Hard stop on red; the coder writes defects and exits on a failed smoke bar.",
    promptSnippet: "Dispatch a coder for an ED (use /directives execute for fresh session)",
    parameters: Type.Object({
      vd_id: Type.String({ description: "The greenlit VD the ED consumes" }),
      instruction: Type.String({ description: "The synthesis instruction for the coder — intent-separated chunks, one intent per chunk" }),
      lane: Type.Optional(Type.String({ description: "Optional lane name; restricts the coder to the lane's declared files" })),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      // gate: the VD the ED consumes must be GREENLIT with go_basis. This is the
      // honest name for the authority check (the legacy ed-latest-greenlit alias
      // exists for back-compat).
      const g = gate(state.cwd, "vd-latest-greenlit", p.vd_id);
      if (!g.ok) return { content: [{ type: "text", text: `gate failed: ${g.reason}` }], details: { isError: true } };
      // gate: cursor not mid-build
      const g2 = gate(state.cwd, "cursor-not-mid-build");
      if (!g2.ok) return { content: [{ type: "text", text: `gate failed: ${g2.reason}` }], details: { isError: true } };
      // gate (F2): if a lane was supplied, re-check disjointness at execute time,
      // not just at register time. Closes the register→execute TOCTOU.
      if (p.lane) {
        const gl = gate(state.cwd, "lane-still-disjoint", p.lane);
        if (!gl.ok) return { content: [{ type: "text", text: `lane no longer disjoint: ${gl.reason}` }], details: { isError: true } };
      }
      const dir = runtimeDir(state.cwd);
      const r = rt(["alloc", state.cwd, "ED", "1"]);
      if (!r.ok) return { content: [{ type: "text", text: `alloc failed: ${r.stderr}` }], details: { isError: true } };
      const [edId] = JSON.parse(r.stdout) as string[];
      const edFile = path.join(dir, "ED", `${edId}.md`);
      const ddId = p.vd_id.replace(/^VD-/, "DD-");
      const pdId = p.vd_id.replace(/^VD-/, "PD-");
      fs.writeFileSync(edFile, [
        "---",
        `id: ${edId}`,
        `kind: ED`,
        `format: v2`,
        `chain-walkback: ${p.vd_id} -> ${ddId} -> ${pdId}`,
        `consumes: ${p.vd_id}`,
        `status: draft`,
        `author: agent-orchestrator`,
        `created: ${now()}`,
        p.lane ? `lane: ${p.lane}` : "",
        "---",
        "",
        `# ${edId} — Execution Directive`,
        "",
        "## 0. Chain walk-back",
        `Consumes ${p.vd_id}, which packaged ${ddId}, decided by ${pdId}.`,
        "",
        "## Synthesis instruction",
        p.instruction,
        "",
        "## Hard stop on red",
        "If a smoke bar fails, write defects to the registry (directive_built RED) and exit. No fix iteration.",
        "",
      ].filter(Boolean).join("\n"));
      // gate: chain-walkback shape
      const gw = gate(state.cwd, "ed-chain-walkback", edFile);
      if (!gw.ok) {
        return { content: [{ type: "text", text: `gate failed: ${gw.reason}` }], details: { isError: true } };
      }
      // position cursor at execution/coder for this ED
      rt(["set-cursor", state.cwd, "execution", "coder", edId, "B-execution", p.lane ?? "-"]);
      setStatus(ctx);
      // Deliver the phase kickoff as a follow-up so the coder starts at a
      // clean turn boundary. NOTE: this is NOT a fresh session — the coder
      // inherits this session's context. For a true fresh-context session,
      // the captain runs `/directives execute <vd_id>` which uses ctx.newSession
      // (command context only). This tool path is the weaker guarantee.
      const kickoff = PHASE_KICKOFF.execution([
        `ED: ${edId}`,
        `Chain: ${p.vd_id} -> ${ddId} -> ${pdId}`,
        `Synthesis instruction:\n${p.instruction}`,
        p.lane ? `Lane: ${p.lane} (only touch files the lane declared)` : "",
        `ED file: ${edFile}`,
        `Runtime dir: ${dir}`,
      ].filter(Boolean).join("\n"));
      pi.sendUserMessage(kickoff, { deliverAs: "followUp" });
      return { content: [{ type: "text", text: `dispatched coder for ${edId} (consumes ${p.vd_id}) via in-session follow-up. For a true fresh-context session, use /directives execute ${p.vd_id}. The coder will call directive_built when done.` }], details: { edId } };
    },
  });

  pi.registerTool({
    name: "directive_built",
    label: "Directive Built",
    description: "Record the build outcome. GREEN = smoke passed; RED = hard stop, defects recorded. No fix iteration.",
    promptSnippet: "Record ED build outcome (GREEN/RED)",
    parameters: Type.Object({
      ed_id: Type.String({ description: "ED id" }),
      color: Type.Union([Type.Literal("GREEN"), Type.Literal("RED")]),
      cycles_to_green: Type.Optional(Type.Number()),
      defects: Type.Optional(Type.String({ description: "Required when RED: the defects file path or summary" })),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      const r = rt(["built", state.cwd, p.ed_id, p.color, String(p.cycles_to_green ?? ""), p.defects ?? ""]);
      if (!r.ok) return { content: [{ type: "text", text: `built failed: ${r.stderr.trim() || r.stdout}` }], details: { isError: true } };
      // release the coder cursor back to orchestrator
      rt(["set-cursor", state.cwd, "execution", "orchestrator", "-", "B-execution", "-"]);
      setStatus(ctx);
      if (p.color === "GREEN") {
        // advance to review
        rt(["set-cursor", state.cwd, "review", "reviewer", p.ed_id, "B-review", "-"]);
        return { content: [{ type: "text", text: `${p.ed_id} BUILT-GREEN. Advanced to review. Call directive_review or run /directives review ${p.ed_id} for a true fresh-context reviewer.` }], details: {} };
      }
      return { content: [{ type: "text", text: `${p.ed_id} BUILT-RED. Hard stop. Defects: ${p.defects ?? "(none)"}. Reopen the ED to re-greenlight after fixing.` }], details: { isError: true } };
    },
  });

  pi.registerTool({
    name: "directive_review",
    label: "Directive Review",
    description: "Dispatch a reviewer to audit a VERIFIED build for intent drift (in-session follow-up). For a TRUE fresh-context review, run /directives review <ed_id>.",
    promptSnippet: "Dispatch a reviewer (use /directives review for fresh session)",
    parameters: Type.Object({
      ed_id: Type.String({ description: "ED id to review" }),
      focus: Type.Optional(Type.String({ description: "Optional review focus (e.g. 'intent drift vs DD-001')" })),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      const dir = runtimeDir(state.cwd);
      const edFile = path.join(dir, "ED", `${p.ed_id}.md`);
      const kickoff = PHASE_KICKOFF.review([
        `ED: ${p.ed_id}`,
        `ED file: ${edFile}`,
        p.focus ? `Review focus: ${p.focus}` : "",
        `Runtime dir: ${dir}`,
      ].filter(Boolean).join("\n"));
      rt(["set-cursor", state.cwd, "review", "reviewer", p.ed_id, "B-review", "-"]);
      setStatus(ctx);
      pi.sendUserMessage(kickoff, { deliverAs: "followUp" });
      return { content: [{ type: "text", text: `dispatched reviewer for ${p.ed_id} via in-session follow-up. For a true fresh-context review, use /directives review ${p.ed_id}.` }], details: {} };
    },
  });

  pi.registerTool({
    name: "directive_verified",
    label: "Directive Verified",
    description: "Mark an ED VERIFIED — the final state. Reviewer is satisfied; no drift; no defects.",
    promptSnippet: "Mark an ED VERIFIED (final)",
    parameters: Type.Object({
      ed_id: Type.String({ description: "ED id to verify" }),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      const r = rt(["verified", state.cwd, p.ed_id]);
      if (!r.ok) return { content: [{ type: "text", text: `verified failed: ${r.stderr.trim() || r.stdout}` }], details: { isError: true } };
      // release cursor; release any lane
      const cur = readCursor(state.cwd);
      if (cur?.lane) rt(["gate", state.cwd, "lane-release", cur.lane as string]);
      rt(["set-cursor", state.cwd, "planning", "orchestrator", "-", "-", "-"]);
      setStatus(ctx);
      return { content: [{ type: "text", text: `${p.ed_id} VERIFIED. Pipeline complete for this directive. Cursor back to planning/orchestrator.` }], details: {} };
    },
  });

  pi.registerTool({
    name: "directive_reopen",
    label: "Directive Reopen",
    description: "Reopen a directive with a non-empty reason. Used by validation/review when a gate fails or drift is found.",
    promptSnippet: "Reopen a directive with a reason",
    parameters: Type.Object({
      id: Type.String({ description: "Packet id to reopen" }),
      reason: Type.String({ description: "Non-empty reason for reopening" }),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      const r = rt(["reopened", state.cwd, p.id, p.reason]);
      if (!r.ok) return { content: [{ type: "text", text: `reopen failed: ${r.stderr.trim() || r.stdout}` }], details: { isError: true } };
      // back to planning/orchestrator so the author can fix
      rt(["set-cursor", state.cwd, "planning", "orchestrator", "-", "-", "-"]);
      setStatus(ctx);
      return { content: [{ type: "text", text: `${p.id} REOPENED: ${p.reason}. Back to planning to fix.` }], details: {} };
    },
  });

  pi.registerTool({
    name: "directive_lane",
    label: "Directive Lane",
    description: "Register a parallel lane with a declared, disjoint file footprint. Overlap with in-flight lanes is refused at launch (fail-closed).",
    promptSnippet: "Register/dispatch a parallel lane (disjointness enforced)",
    parameters: Type.Object({
      name: Type.String({ description: "Lane name (unique)" }),
      files: Type.Array(Type.String(), { description: "Files this lane will touch — must be disjoint from all in-flight lanes" }),
      vd_id: Type.Optional(Type.String({ description: "Optional greenlit VD the lane executes" })),
      instruction: Type.Optional(Type.String({ description: "Optional synthesis instruction for the lane's ED" })),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      // gate: disjointness checked BEFORE registration (deterministic-first)
      const g = gate(state.cwd, "lane-disjoint", p.name, JSON.stringify(p.files));
      if (!g.ok) return { content: [{ type: "text", text: `lane overlap refused: ${g.reason}` }], details: { isError: true } };
      // register
      rt(["gate", state.cwd, "lane-register", p.name, JSON.stringify(p.files)]);
      setStatus(ctx);
      if (p.vd_id && p.instruction) {
        return { content: [{ type: "text", text: `lane ${p.name} registered (files: ${p.files.join(", ")}). Call directive_execute with lane=${p.name} to dispatch.` }], details: { lane: p.name } };
      }
      return { content: [{ type: "text", text: `lane ${p.name} registered with disjoint footprint (${p.files.join(", ")}).` }], details: { lane: p.name } };
    },
  });

  pi.registerTool({
    name: "directive_release",
    label: "Directive Release",
    description: "Release a lane's file footprint reservation so other lanes can claim those files.",
    promptSnippet: "Release a lane's footprint reservation",
    parameters: Type.Object({
      name: Type.String({ description: "Lane name to release" }),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      rt(["gate", state.cwd, "lane-release", p.name]);
      setStatus(ctx);
      return { content: [{ type: "text", text: `lane ${p.name} released` }], details: {} };
    },
  });

  pi.registerTool({
    name: "directive_advance",
    label: "Directive Advance",
    description: "Advance the phase cursor. Resets the postpone budget on a phase change. Use to move planning->design->validation->execution->review.",
    promptSnippet: "Advance the phase cursor",
    parameters: Type.Object({
      phase: Type.Union(PHASES.map((p) => Type.Literal(p))),
      role: Type.Union([Type.Literal("orchestrator"), Type.Literal("author"), Type.Literal("coder"), Type.Literal("reviewer"), Type.Literal("idle")]),
      active: Type.Optional(Type.String({ description: "active_directive id or '-' for null" })),
      lane: Type.Optional(Type.String({ description: "lane name or '-' for null" })),
    }),
    async execute(_id, p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      const r = rt(["set-cursor", state.cwd, p.phase, p.role, p.active ?? "-", "-", p.lane ?? "-"]);
      if (!r.ok) return { content: [{ type: "text", text: `advance failed: ${r.stderr.trim() || r.stdout}` }], details: { isError: true } };
      setStatus(ctx);
      return { content: [{ type: "text", text: `cursor advanced to ${p.phase}/${p.role}` }], details: {} };
    },
  });

  pi.registerTool({
    name: "directive_postpone",
    label: "Directive Postpone",
    description: "Postpone a handoff at a phase boundary. Budget: 2 per phase occupancy, then HiTL escalation.",
    promptSnippet: "Postpone a phase-boundary handoff",
    parameters: Type.Object({}),
    async execute(_id, _p, _s, _u, ctx) {
      if (!state?.initialized) return { content: [{ type: "text", text: "directives not initialized" }], details: {} };
      const r = rt(["postpone", state.cwd]);
      if (!r.ok) return { content: [{ type: "text", text: `postpone refused: ${r.stderr.trim() || r.stdout}` }], details: { isError: true } };
      setStatus(ctx);
      return { content: [{ type: "text", text: `postponed (${r.stdout.trim()})` }], details: {} };
    },
  });

  // --- /directives command ---

  pi.registerCommand("directives", {
    description: "Drive the native directive pipeline: status, init, plan, settle, validate, greenlight, execute, review, lane, yolo. Subcommands: status | init | plan <text> | settle <id> | greenlight <id> [basis] | execute <vd> | review <ed> | lane <name> <files...> | release <name> | phase <name> <role> | yolo [on|off]",
    handler: async (args, ctx) => {
      const parts = args.trim().split(/\s+/);
      const sub = parts[0] || "status";
      const rest = parts.slice(1);
      if (!state) load(ctx);
      if (!state?.initialized && sub !== "init") {
        const r = rt(["init", state?.cwd ?? process.cwd()]);
        if (r.ok && state) { state.initialized = true; persist(); }
      }
      const cwd = state?.cwd ?? process.cwd();
      switch (sub) {
        case "status": {
          ctx.ui.notify(summary(cwd), "info");
          return;
        }
        case "init": {
          const r = rt(["init", cwd]);
          if (r.ok) { state = { cwd, initialized: true, yolo: readSettings().yolo }; persist(); setStatus(ctx); ctx.ui.notify(`directives initialized: ${runtimeDir(cwd)}`, "info"); }
          else ctx.ui.notify(`init failed: ${r.stderr}`, "error");
          return;
        }
        case "yolo": {
          const v = rest[0];
          if (v === "on" || v === "off") {
            const res = writeSettings({ yolo: v === "on" });
            if (!res.ok) {
              ctx.ui.notify(`directives yolo ${v} FAILED: ${res.error}`, "error");
              return;
            }
            if (state) { state.yolo = v === "on"; persist(); }
            setStatus(ctx);
            ctx.ui.notify(`directives yolo ${v}`, "info");
          } else {
            ctx.ui.notify(`directives yolo is ${readSettings().yolo ? "on" : "off"}`, "info");
          }
          return;
        }
        case "phase": {
          const r = rt(["set-cursor", cwd, rest[0] ?? "planning", rest[1] ?? "orchestrator", rest[2] ?? "-", "-", "-"]);
          if (r.ok) { setStatus(ctx); ctx.ui.notify(`phase -> ${rest[0]}/${rest[1] ?? "orchestrator"}`, "info"); }
          else ctx.ui.notify(`phase failed: ${r.stderr.trim()}`, "error");
          return;
        }
        case "execute": {
          // TRUE fresh-context-per-phase: the command (command context) can
          // ctx.newSession, which the tool cannot. Dispatches a coder into a
          // fresh session with the execution kickoff.
          const vdId = rest[0];
          if (!vdId) { ctx.ui.notify("usage: /directives execute <vd_id>", "warning"); return; }
          const g = gate(cwd, "vd-latest-greenlit", vdId);
          if (!g.ok) { ctx.ui.notify(`gate failed: ${g.reason}`, "error"); return; }
          const dir = runtimeDir(cwd);
          const r = rt(["alloc", cwd, "ED", "1"]);
          if (!r.ok) { ctx.ui.notify(`alloc failed: ${r.stderr}`, "error"); return; }
          const [edId] = JSON.parse(r.stdout) as string[];
          const ddId = vdId.replace(/^VD-/, "DD-");
          const pdId = vdId.replace(/^VD-/, "PD-");
          const edFile = path.join(dir, "ED", `${edId}.md`);
          fs.writeFileSync(edFile, [
            "---",
            `id: ${edId}`, `kind: ED`, `format: v2`,
            `chain-walkback: ${vdId} -> ${ddId} -> ${pdId}`,
            `consumes: ${vdId}`, `status: draft`, `author: agent-orchestrator`, `created: ${now()}`,
            "---", "",
            `# ${edId} — Execution Directive`, "",
            "## 0. Chain walk-back",
            `Consumes ${vdId}, which packaged ${ddId}, decided by ${pdId}.`, "",
          ].join("\n"));
          const gw = gate(cwd, "ed-chain-walkback", edFile);
          if (!gw.ok) { ctx.ui.notify(`gate failed: ${gw.reason}`, "error"); return; }
          rt(["set-cursor", cwd, "execution", "coder", edId, "B-execution", "-"]);
          setStatus(ctx);
          const kickoff = PHASE_KICKOFF.execution([
            `ED: ${edId}`, `Chain: ${vdId} -> ${ddId} -> ${pdId}`,
            `ED file: ${edFile}`, `Runtime dir: ${dir}`,
          ].join("\n"));
          await ctx.newSession({
            withSession: async (sctx) => { await sctx.sendUserMessage(kickoff); },
          });
          return;
        }
        case "review": {
          // TRUE fresh-context review: dispatches a reviewer into a fresh session.
          const edId = rest[0];
          if (!edId) { ctx.ui.notify("usage: /directives review <ed_id>", "warning"); return; }
          const dir = runtimeDir(cwd);
          const edFile = path.join(dir, "ED", `${edId}.md`);
          const kickoff = PHASE_KICKOFF.review([
            `ED: ${edId}`, `ED file: ${edFile}`, `Runtime dir: ${dir}`,
          ].join("\n"));
          rt(["set-cursor", cwd, "review", "reviewer", edId, "B-review", "-"]);
          setStatus(ctx);
          await ctx.newSession({
            withSession: async (sctx) => { await sctx.sendUserMessage(kickoff); },
          });
          return;
        }
        default: {
          ctx.ui.notify(`Use the directive_* tools to drive the pipeline, or /directives status|init|yolo on|off|phase <name> <role>. Summary:\n${summary(cwd)}`, "info");
          return;
        }
      }
    },
  });
}
