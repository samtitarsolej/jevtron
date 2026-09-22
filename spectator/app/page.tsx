"use client";

import { useEffect, useRef, useState } from "react";

const SERVER = process.env.NEXT_PUBLIC_SERVER || "http://localhost:8000";
const WS = SERVER.replace(/^http/, "ws");

const HEAD: Record<string, string> = { A: "#ff4d6d", B: "#4dd2ff", C: "#ffd166", D: "#8aff80" };
const TRAIL: Record<string, string> = { "0": "#8c2b3d", "1": "#276d85", "2": "#8a6c1f", "3": "#43863d" };
const PLAYER_COLOR = ["#ff4d6d", "#4dd2ff", "#ffd166", "#8aff80"];

type Meter = {
  id: string; tokens_used: number; budget: number; calls: number;
  last_latency_ms: number; missed_ticks: number; connected: boolean;
};
type Frame = { tick: number; grid: string[]; players: any[] };

function Arena({ grid }: { grid: string[] }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv || !grid.length) return;
    const w = grid[0].length, h = grid.length;
    const cell = Math.max(4, Math.floor(Math.min(640 / w, 640 / h)));
    cv.width = w * cell;
    cv.height = h * cell;
    const ctx = cv.getContext("2d")!;
    ctx.fillStyle = "#0b0e14";
    ctx.fillRect(0, 0, cv.width, cv.height);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const c = grid[y][x];
        let color = null as string | null;
        if (c === "#") color = "#2a3040";
        else if (c === "*") color = "#ffffff";
        else if (c === "?") color = "#12161f";
        else if (TRAIL[c]) color = TRAIL[c];
        else if (HEAD[c]) color = HEAD[c];
        if (!color) continue;
        ctx.fillStyle = color;
        ctx.fillRect(x * cell, y * cell, cell - (cell > 6 ? 1 : 0), cell - (cell > 6 ? 1 : 0));
      }
    }
  }, [grid]);
  return <canvas ref={ref} style={{ border: "1px solid #232a38", borderRadius: 6 }} />;
}

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min(100, (value / Math.max(max, 1)) * 100);
  return (
    <div style={{ background: "#1b2130", height: 8, borderRadius: 4, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color }} />
    </div>
  );
}

function Panels({ meters, players }: { meters: Meter[]; players: any[] }) {
  return (
    <div style={{ display: "grid", gap: 10, minWidth: 280 }}>
      {meters.map((m, i) => {
        const p = players.find((x) => x.id === m.id) || {};
        const color = PLAYER_COLOR[i % 4];
        return (
          <div key={m.id} style={{ border: "1px solid #232a38", borderRadius: 6, padding: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <b style={{ color }}>
                {"ABCD"[i]} · {m.id}
              </b>
              <span style={{ color: p.alive ? "#8aff80" : "#6a7385" }}>
                {p.alive ? "alive" : "dead"}
                {m.connected ? "" : " · offline"}
              </span>
            </div>
            <div style={{ fontSize: 12, color: "#8b94a7", margin: "6px 0 3px" }}>
              tokens {m.tokens_used} / {m.budget} · {m.calls} calls
            </div>
            <Bar value={m.tokens_used} max={m.budget} color={color} />
            <div style={{ fontSize: 12, color: "#8b94a7", marginTop: 6 }}>
              last jev {m.last_latency_ms}ms · missed {m.missed_ticks} · trail {p.trail_len ?? 0}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Live() {
  const [msg, setMsg] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    const ws = new WebSocket(`${WS}/ws/spectate`);
    ws.onmessage = (e) => setMsg(JSON.parse(e.data));
    ws.onerror = () => setErr("cannot reach server");
    ws.onclose = () => setErr("disconnected — reload to follow the next match");
    return () => ws.close();
  }, []);
  if (!msg) return <p>{err || "waiting for a match…"}</p>;
  if (msg.type === "error") return <p>{msg.error}</p>;
  const st = msg.state;
  return (
    <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
      <div>
        <div style={{ marginBottom: 8 }}>
          match <b>{msg.match_id}</b> · {msg.status} · tick {st.tick}
          {st.shrink ? ` · shrink ${st.shrink}` : ""}
        </div>
        <Arena grid={st.grid} />
        {msg.result && (
          <pre style={{ color: "#8aff80" }}>
            winner: {msg.result.winner.join(", ") || "nobody"}
          </pre>
        )}
      </div>
      <Panels meters={msg.meters} players={st.players} />
      {err && <p style={{ color: "#ff4d6d" }}>{err}</p>}
    </div>
  );
}

function Leaderboard() {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => {
    const load = () =>
      fetch(`${SERVER}/leaderboard`).then((r) => r.json()).then((d) => setRows(d.leaderboard)).catch(() => {});
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);
  return (
    <table style={{ borderSpacing: "16px 6px" }}>
      <thead>
        <tr style={{ color: "#8b94a7" }}>
          <th align="left">#</th><th align="left">player</th><th align="right">score</th><th align="right">style</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.id}>
            <td>{i + 1}</td><td>{r.id}</td>
            <td align="right">{r.score.toFixed(3)}</td>
            <td align="right">{r.style_bonus}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Replay() {
  const [ids, setIds] = useState<string[]>([]);
  const [replay, setReplay] = useState<any>(null);
  const [i, setI] = useState(0);
  useEffect(() => {
    fetch(`${SERVER}/replays`).then((r) => r.json()).then((d) => setIds(d.replays)).catch(() => {});
  }, []);
  const load = (id: string) =>
    fetch(`${SERVER}/replays/${id}`).then((r) => r.json()).then((d) => { setReplay(d); setI(0); });
  const frame: Frame | null = replay ? replay.ticks[i].state : null;
  return (
    <div>
      <select onChange={(e) => e.target.value && load(e.target.value)} defaultValue="">
        <option value="">pick a replay…</option>
        {ids.map((id) => <option key={id} value={id}>{id}</option>)}
      </select>
      {frame && (
        <div style={{ marginTop: 12 }}>
          <input
            type="range" min={0} max={replay.ticks.length - 1} value={i}
            onChange={(e) => setI(Number(e.target.value))} style={{ width: 640 }}
          />
          <div style={{ marginBottom: 8 }}>
            tick {frame.tick} / {replay.ticks.length - 1} · {replay.players.join(", ")}
          </div>
          <Arena grid={frame.grid} />
          <pre style={{ color: "#8b94a7" }}>
            {JSON.stringify(replay.ticks[i].tokens || {}, null, 1)}
          </pre>
        </div>
      )}
    </div>
  );
}

const btn: React.CSSProperties = {
  background: "#1b2130", color: "#d7dce5", border: "1px solid #2a3040",
  borderRadius: 4, padding: "6px 10px", cursor: "pointer",
};
const input: React.CSSProperties = {
  background: "#0f131c", color: "#d7dce5", border: "1px solid #2a3040",
  borderRadius: 4, padding: "6px 8px",
};
const card: React.CSSProperties = { border: "1px solid #232a38", borderRadius: 6, padding: 12 };

function useStored(key: string, initial: string) {
  const [v, setV] = useState(initial);
  useEffect(() => { const s = localStorage.getItem(key); if (s !== null) setV(s); }, [key]);
  const set = (x: string) => { setV(x); localStorage.setItem(key, x); };
  return [v, set] as const;
}

function inviteFor(pid: string, token: string, matchId: string, url: string, repo: string, health: any) {
  return [
    `Jev-Tron Arena — you are "${pid}"`,
    ``,
    `Server : ${url}`,
    `Token  : ${token}`,
    `Match  : ${matchId}`,
    ``,
    `git clone ${repo} && cd jevtron`,
    `python3 -m venv .venv && . .venv/bin/activate && pip install -e ./sdk`,
    `PLAYER_TOKEN=${token} JEVTRON_SERVER=${url} python sdk/bot_template.py`,
    ``,
    `Then copy sdk/bot_template.py to my_bot.py and make it yours.`,
    ``,
    `Rules: docs/RULES.md · SDK: docs/SDK.md`,
    `Budget: ${health?.budget ?? "unlimited (clone server)"} tokens/match · ` +
      `Turn deadline: ${health?.deadline_ms ?? 3000} ms`,
  ].join("\n");
}

function GM() {
  const [pw, setPw] = useStored("jevtron.gm.pw", "");
  const [repo, setRepo] = useStored("jevtron.repo", "<repo url>");
  const [players, setPlayers] = useStored("jevtron.players", "alice,bob,cid,dee");
  const [rounds, setRounds] = useStored("jevtron.rounds", "1");
  const [deadline, setDeadline] = useStored("jevtron.deadline", "3000");
  const [list, setList] = useState<any[]>([]);
  const [selected, setSelected] = useState("");
  const [tokens, setTokens] = useState<Record<string, string>>({});
  const [health, setHealth] = useState<any>(null);
  const [note, setNote] = useState("");

  const headers = { "content-type": "application/json", "x-gm-password": pw };
  const post = async (path: string, body?: any) => {
    const r = await fetch(`${SERVER}${path}`, { method: "POST", headers, body: JSON.stringify(body ?? {}) });
    const d = await r.json().catch(() => ({}));
    setNote(r.ok ? "ok" : `${r.status}: ${d.detail ?? "failed"}`);
    return r.ok ? d : null;
  };

  useEffect(() => {
    fetch(`${SERVER}/health`).then((r) => r.json()).then(setHealth).catch(() => {});
    const load = () => fetch(`${SERVER}/matches`).then((r) => r.json())
      .then((d) => setList(d.matches)).catch(() => {});
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!selected || !pw) return;
    fetch(`${SERVER}/matches/${selected}/tokens`, { headers })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setTokens(d.tokens))
      .catch(() => {});
  }, [selected, pw]);

  const joinUrl = health?.lan_ip ? SERVER.replace(/\/\/[^:/]+/, `//${health.lan_ip}`) : SERVER;
  const match = list.find((m) => m.match_id === selected);
  const connected = match ? match.meters.filter((x: any) => x.connected).length : 0;
  const ready = match && connected === match.players.length;
  const copy = (text: string, what: string) => {
    navigator.clipboard.writeText(text).then(() => setNote(`copied ${what}`), () => setNote("copy blocked"));
  };

  const create = async () => {
    const ids = players.split(",").map((s) => s.trim()).filter(Boolean);
    const body: any = { players: ids, deadline_ms: Number(deadline) };
    const n = Number(rounds);
    const d = n > 1 ? await post("/tournament", { ...body, rounds: n }) : await post("/matches", body);
    const made = d && (d.matches ? d.matches[0] : d);
    if (made) { setSelected(made.match_id); setTokens(made.tokens); }
  };

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 900 }}>
      <div style={{ ...card, display: "grid", gap: 8 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input style={{ ...input, flex: 1 }} type="password" placeholder="GM password"
                 value={pw} onChange={(e) => setPw(e.target.value)} />
          <input style={{ ...input, flex: 2 }} placeholder="repo url for the invite"
                 value={repo} onChange={(e) => setRepo(e.target.value)} />
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input style={{ ...input, flex: 2 }} placeholder="players, comma separated"
                 value={players} onChange={(e) => setPlayers(e.target.value)} />
          <label style={{ fontSize: 12, color: "#8b94a7" }}>rounds</label>
          <input style={{ ...input, width: 60 }} value={rounds} onChange={(e) => setRounds(e.target.value)} />
          <label style={{ fontSize: 12, color: "#8b94a7" }}>deadline ms</label>
          <input style={{ ...input, width: 80 }} value={deadline} onChange={(e) => setDeadline(e.target.value)} />
          <button style={btn} onClick={create}>create {Number(rounds) > 1 ? "tournament" : "match"}</button>
        </div>
        <div style={{ fontSize: 12, color: "#8b94a7" }}>
          contestants connect to <b>{joinUrl}</b>
          {health && ` · ${health.mode} mode${health.jev_mock ? " · MOCK Jev" : ""}`}
          {note && <span style={{ color: note === "ok" || note.startsWith("copied") ? "#8aff80" : "#ff4d6d" }}> · {note}</span>}
        </div>
      </div>

      <div style={card}>
        <div style={{ color: "#8b94a7", fontSize: 12, marginBottom: 8 }}>matches — click one to run it</div>
        <div style={{ display: "grid", gap: 4, maxHeight: 200, overflow: "auto" }}>
          {list.length === 0 && <span style={{ color: "#6a7385" }}>none yet</span>}
          {list.map((m) => (
            <div key={m.match_id} onClick={() => setSelected(m.match_id)}
                 style={{
                   display: "flex", gap: 12, cursor: "pointer", padding: "4px 6px", borderRadius: 4,
                   background: m.match_id === selected ? "#2a3040" : "transparent",
                 }}>
              <span style={{ width: 80 }}>{m.match_id}</span>
              <span style={{ width: 70, color: m.status === "running" ? "#8aff80" : "#8b94a7" }}>{m.status}</span>
              <span style={{ width: 70 }}>tick {m.tick}</span>
              <span style={{ width: 90 }}>
                {m.meters.filter((x: any) => x.connected).length}/{m.players.length} connected
              </span>
              <span style={{ color: "#8b94a7" }}>{m.players.join(", ")}</span>
            </div>
          ))}
        </div>
      </div>

      {match && (
        <>
          <div style={{ ...card, display: "grid", gap: 10 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <b>{match.match_id}</b>
              <span style={{ color: ready ? "#8aff80" : "#ffd166" }}>
                {connected}/{match.players.length} connected
              </span>
              <button style={{ ...btn, opacity: match.status === "lobby" ? 1 : 0.4 }}
                      disabled={match.status !== "lobby"}
                      onClick={() => post(`/matches/${match.match_id}/start`)}>
                {ready ? "start match" : `start anyway (${match.players.length - connected} missing)`}
              </button>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: "#8b94a7", alignSelf: "center" }}>curveballs:</span>
              <button style={btn} onClick={() => post(`/matches/${match.match_id}/curveball`, { fog_radius: 5 })}>fog 5</button>
              <button style={btn} onClick={() => post(`/matches/${match.match_id}/curveball`, { shrink_every: 20 })}>shrink /20</button>
              <button style={btn} onClick={() => post(`/matches/${match.match_id}/curveball`, { bonus_tiles: 5 })}>+5 bonus</button>
              <button style={btn} onClick={() => post(`/matches/${match.match_id}/curveball`, { fog_radius: 0, shrink_every: 0 })}>clear</button>
            </div>
          </div>

          <div style={{ ...card, display: "grid", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#8b94a7", fontSize: 12 }}>invites — one per contestant</span>
              <button style={btn} onClick={() => copy(
                Object.entries(tokens).map(([pid, t]) =>
                  inviteFor(pid, t, match.match_id, joinUrl, repo, health)).join("\n\n---\n\n"),
                "all invites")}>copy all</button>
            </div>
            {Object.entries(tokens).map(([pid, token]) => (
              <div key={pid} style={{ display: "grid", gap: 4 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <b style={{ width: 90 }}>{pid}</b>
                  <code style={{ color: "#8b94a7", flex: 1 }}>{token}</code>
                  <button style={btn} onClick={() => copy(token, `${pid}'s token`)}>token</button>
                  <button style={btn} onClick={() => copy(
                    inviteFor(pid, token, match.match_id, joinUrl, repo, health), `${pid}'s invite`)}>invite</button>
                  <input style={{ ...input, width: 60 }} placeholder="style"
                         onKeyDown={(e: any) => e.key === "Enter" &&
                           post(`/players/${pid}/style_bonus`, { value: Number(e.target.value) })} />
                </div>
              </div>
            ))}
            {!Object.keys(tokens).length && (
              <span style={{ color: "#6a7385" }}>enter the GM password to load tokens</span>
            )}
          </div>

          {match.result && (
            <pre style={{ ...card, color: "#8b94a7", overflow: "auto", maxHeight: 220 }}>
              {JSON.stringify(match.result.players, null, 1)}
            </pre>
          )}
        </>
      )}
    </div>
  );
}

export default function Page() {
  const [tab, setTab] = useState("live");
  const tabs = ["live", "leaderboard", "replay", "gm"];
  return (
    <main style={{ padding: 20 }}>
      <h1 style={{ margin: "0 0 4px" }}>Jev-Tron Arena</h1>
      <div style={{ color: "#8b94a7", fontSize: 12, marginBottom: 14 }}>{SERVER}</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: tab === t ? "#2a3040" : "#131823",
              color: "#d7dce5", border: "1px solid #2a3040",
              borderRadius: 4, padding: "6px 12px", cursor: "pointer",
            }}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "live" && <Live />}
      {tab === "leaderboard" && <Leaderboard />}
      {tab === "replay" && <Replay />}
      {tab === "gm" && <GM />}
    </main>
  );
}
