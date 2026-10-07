// Client for the FastAPI backend (app/api/main.py). In dev, Vite proxies /api -> http://localhost:8000.
const BASE = import.meta.env.VITE_API_URL ?? "/api"

export type Direction = "in" | "out"

/** One plate found in an image (alpr.types.PlateResult). */
export interface PlateResult {
  box: [number, number, number, number] // x1, y1, x2, y2 in image pixels
  det_conf: number
  text: string // normalized, e.g. "51G12345"
  display: string // human readable, e.g. "51G-123.45"
  ocr_conf: number
  valid: boolean // matches a VN plate template
  two_line: boolean
  raw_lines: string[]
  track_id: number | null
}

/** A row of the events table (app/db/repository.py). */
export interface GateEvent {
  id: number
  plate: string
  display: string
  direction: Direction
  gate: string
  confidence: number
  image_path: string | null
  created_at: string
  duration_s?: number // only on an exit that follows an entry
}

export interface RecognizeResponse {
  plates: PlateResult[]
  latency_ms: number
}

export interface GateResponse extends RecognizeResponse {
  events: GateEvent[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
    } catch {
      // non-JSON error body (e.g. "Internal Server Error")
    }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

function imageForm(file: File): FormData {
  const form = new FormData()
  form.append("file", file)
  return form
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  recognize: (file: File) => request<RecognizeResponse>("/recognize", { method: "POST", body: imageForm(file) }),

  gate: (direction: Direction, file: File, gate = "main") =>
    request<GateResponse>(`/gate/${direction}?gate=${encodeURIComponent(gate)}`, {
      method: "POST",
      body: imageForm(file),
    }),

  events: (plate?: string, limit = 100) => {
    const q = new URLSearchParams({ limit: String(limit) })
    if (plate) q.set("plate", plate)
    return request<GateEvent[]>(`/events?${q}`)
  },

  parked: () => request<GateEvent[]>("/parked"),
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h) return `${h} giờ ${m} phút`
  if (m) return `${m} phút ${s} giây`
  return `${s} giây`
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN")
}
