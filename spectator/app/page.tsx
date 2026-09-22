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

function GM() {
  const [pw, setPw] = useState("");
  const [players, setPlayers] = useState("alice,bob,cid,dee");
  const [matchId, setMatchId] = useState("");
  const [out, setOut] = useState<any>(null);
  const call = (path: string, body?: any) =>
    fetch(`${SERVER}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-gm-password": pw },
      body: JSON.stringify(body ?? {}),
    }).then((r) => r.json()).then(setOut).catch((e) => setOut(String(e)));

  const btn = { background: "#1b2130", color: "#d7dce5", border: "1px solid #2a3040", borderRadius: 4, padding: "6px 10px", cursor: "pointer" };
  return (
    <div style={{ display: "grid", gap: 10, maxWidth: 640 }}>
      <input placeholder="GM password" value={pw} onChange={(e) => setPw(e.target.value)} type="password" />
      <input placeholder="players, comma separated" value={players} onChange={(e) => setPlayers(e.target.value)} />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button style={btn} onClick={() => call("/matches", { players: players.split(",").map((s) => s.trim()) })}>
          create match
        </button>
        <input placeholder="match id" value={matchId} onChange={(e) => setMatchId(e.target.value)} />
        <button style={btn} onClick={() => call(`/matches/${matchId}/start`)}>start</button>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button style={btn} onClick={() => call(`/matches/${matchId}/curveball`, { fog_radius: 5 })}>fog 5</button>
        <button style={btn} onClick={() => call(`/matches/${matchId}/curveball`, { shrink_every: 20 })}>shrink /20</button>
        <button style={btn} onClick={() => call(`/matches/${matchId}/curveball`, { bonus_tiles: 5 })}>+5 bonus tiles</button>
      </div>
      <StyleBonus call={call} btn={btn} />
      <pre style={{ color: "#8b94a7", maxHeight: 240, overflow: "auto" }}>{JSON.stringify(out, null, 1)}</pre>
    </div>
  );
}

function StyleBonus({ call, btn }: { call: any; btn: any }) {
  const [pid, setPid] = useState("");
  const [value, setValue] = useState("0.5");
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <input placeholder="player id" value={pid} onChange={(e) => setPid(e.target.value)} />
      <input placeholder="0..1" value={value} onChange={(e) => setValue(e.target.value)} style={{ width: 70 }} />
      <button style={btn} onClick={() => call(`/players/${pid}/style_bonus`, { value: Number(value) })}>
        set style bonus
      </button>
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
