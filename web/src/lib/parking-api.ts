// Client for the parking lot routes (app/api/parking.py, /parking/*).
import { BASE, request, type PlateResult } from "@/lib/api"

export type VehicleType = "motorbike" | "car"

/** Look of a vehicle in the 3D scene, chosen by the user when the vehicle arrives. */
export interface VehicleStyle {
  model: string
  color: string
}

export interface Fee {
  base: number
  base_hours: number
  per_hour: number
  lost_card: number
}

/** One parking visit (app/parking/lot.py, sessions table). */
export interface Session {
  id: number
  card_id: number
  card_code: string
  slot_id: string
  vehicle_type: VehicleType
  vehicle_style: Partial<VehicleStyle>
  plate: string // normalized, e.g. "54L19999"
  display: string // as confirmed by the driver, e.g. "54-L1 9999"
  plate_ocr: string // what the model read at the entry
  ocr_conf: number
  edited: boolean // the driver corrected the model
  entry_capture: number | null
  entry_time: string
  exit_capture: number | null
  exit_plate_ocr: string | null
  exit_match: MatchStatus | null
  exit_time: string | null
  fee: number | null
  lost_card: boolean
  override_reason: string | null
  status: "parked" | "exited"
}

export interface Slot {
  id: string // M01..M20, C01..C10
  vehicle_type: VehicleType
  session: Session | null
}

export interface LotState {
  name: string
  now: string
  time_offset_h: number
  allow_time_travel: boolean
  cards: {
    available: number
    in_use: number
    locked: number
    locked_ids: number[]
    next: number | null
    next_code: string | null
  }
  capacity: Record<VehicleType, { total: number; free: number }>
  slots: Slot[]
  fees: Record<VehicleType, Fee>
}

export interface Capture {
  id: number
  plates: PlateResult[]
  created_at: string
}

export type MatchStatus = "ok" | "suspect" | "mismatch"

export interface ExitCheck {
  session: Session
  capture: Capture
  match: { status: MatchStatus; read: string; distance: number; reason: string }
  fee: number
  lost_card: boolean
  exit_time: string
  duration_s: number
}

export interface Stats {
  parked: Record<VehicleType, number>
  today: { entries: number; exits: number; revenue: number }
  revenue_total: number
  entries_total: number
  ocr_edit_rate: number | null
  corrections: number
  overrides: number
  lost_cards: number
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
})

export const parkingApi = {
  lot: () => request<LotState>("/parking/lot"),
  stats: () => request<Stats>("/parking/stats"),
  sessions: (status?: "parked" | "exited", limit = 50) => {
    const q = new URLSearchParams({ limit: String(limit) })
    if (status) q.set("status", status)
    return request<Session[]>(`/parking/sessions?${q}`)
  },

  capture: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return request<{ capture: Capture; latency_ms: number }>("/parking/captures", { method: "POST", body: form })
  },
  imageUrl: (captureId: number) => `${BASE}/parking/captures/${captureId}/image`,

  validate: (text: string) =>
    request<{ valid: boolean; text: string; display: string }>("/parking/plates/validate", json({ text })),

  enter: (body: { card_id: number; plate: string; vehicle_type: VehicleType; capture_id: number; style: VehicleStyle }) =>
    request<Session>("/parking/entry", json(body)),

  checkExit: (body: { capture_id: number; card_id?: number; plate?: string; lost_card?: boolean }) =>
    request<ExitCheck>("/parking/exit/check", json(body)),

  confirmExit: (body: { session_id: number; capture_id: number; lost_card?: boolean; override_reason?: string }) =>
    request<Session>("/parking/exit/confirm", json(body)),

  restoreCard: (cardId: number) => request<LotState["cards"]>(`/parking/cards/${cardId}/restore`, { method: "POST" }),
  travel: (hours: number) => request<{ now: string }>("/parking/clock", json({ hours })),
  exportCorrections: (editedOnly: boolean) =>
    request<{ lines: number; out: string }>("/parking/corrections/export", json({ edited_only: editedOnly })),
}

export const VEHICLE_LABEL: Record<VehicleType, string> = { motorbike: "Xe máy", car: "Ô tô" }

export function formatVnd(amount: number): string {
  return `${amount.toLocaleString("vi-VN")}đ`
}
