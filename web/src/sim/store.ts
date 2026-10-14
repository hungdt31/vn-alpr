import { create } from "zustand"

import { parkingApi, type Capture, type LotState, type Session } from "@/lib/parking-api"
import type { VehicleSpec } from "@/sim/vehicles"

/**
 * One vehicle is handled at a time. The phase drives both the 3D scene (who moves where, which barrier
 * is open) and the dialogs (which one is open), so they never disagree.
 *
 * entry: choose -> arriving -> entry-recognize -> entry-card -> entry-confirm -> entering -> idle
 *                                     └──────────── cancel ─────────────┴──> turning-away -> idle
 * exit:  exit-pick -> to-exit -> exit-check -> exiting -> idle
 *                                     └── guard holds the vehicle -> back-to-slot -> idle
 */
export type Phase =
  | { kind: "idle" }
  | { kind: "choose" }
  | { kind: "arriving"; spec: VehicleSpec }
  | { kind: "entry-recognize"; spec: VehicleSpec }
  | { kind: "entry-card"; spec: VehicleSpec; capture: Capture; plate: string }
  | { kind: "entry-confirm"; spec: VehicleSpec; capture: Capture; plate: string; cardId: number; cardCode: string }
  | { kind: "entering"; spec: VehicleSpec; plate: string; slotId: string; sessionId: number }
  | { kind: "turning-away"; spec: VehicleSpec; plate?: string }
  | { kind: "exit-pick" }
  | { kind: "to-exit"; session: Session }
  | { kind: "exit-check"; session: Session }
  | { kind: "exiting"; session: Session }
  | { kind: "back-to-slot"; session: Session }

type Kind = Phase["kind"]
const ENTRY_AT_GATE: Kind[] = ["entry-recognize", "entry-card", "entry-confirm"]

interface SimState {
  phase: Phase
  lot: LotState | null
  lotError: string | null
  /** bumped each time a ticket leaves the dispenser, to replay the pop-out animation */
  cardPop: number
  refresh: () => Promise<void>
  setPhase: (phase: Phase) => void
  /** an animation finished: move to the phase that follows it */
  arrived: () => void
  takeCard: () => void
  confirmEntry: () => Promise<Session>
  cancelEntry: () => void
  pickSession: (session: Session) => void
  release: () => void
  hold: () => void
}

export const useSim = create<SimState>((set, get) => ({
  phase: { kind: "idle" },
  lot: null,
  lotError: null,
  cardPop: 0,

  refresh: async () => {
    try {
      set({ lot: await parkingApi.lot(), lotError: null })
    } catch (e) {
      set({ lotError: (e as Error).message })
    }
  },

  setPhase: (phase) => set({ phase }),

  arrived: () => {
    const p = get().phase
    switch (p.kind) {
      case "arriving":
        return set({ phase: { kind: "entry-recognize", spec: p.spec } })
      case "to-exit":
        return set({ phase: { kind: "exit-check", session: p.session } })
      case "entering":
      case "exiting":
      case "back-to-slot":
      case "turning-away":
        set({ phase: { kind: "idle" } })
        void get().refresh()
    }
  },

  takeCard: () => {
    const { phase: p, lot } = get()
    if (p.kind !== "entry-card" || !lot?.cards.next || !lot.cards.next_code) return
    set((s) => ({
      cardPop: s.cardPop + 1,
      phase: { ...p, kind: "entry-confirm", cardId: lot.cards.next!, cardCode: lot.cards.next_code! },
    }))
  },

  confirmEntry: async () => {
    const p = get().phase
    if (p.kind !== "entry-confirm") throw new Error("Không có xe nào đang chờ vào")
    const session = await parkingApi.enter({
      card_id: p.cardId,
      plate: p.plate,
      vehicle_type: p.spec.type,
      capture_id: p.capture.id,
      style: { model: p.spec.model, color: p.spec.color },
    })
    set({
      phase: { kind: "entering", spec: p.spec, plate: session.display, slotId: session.slot_id, sessionId: session.id },
    })
    void get().refresh() // the slot shows as taken while the vehicle drives there
    return session
  },

  cancelEntry: () => {
    const p = get().phase
    if (p.kind === "choose") return set({ phase: { kind: "idle" } })
    if (ENTRY_AT_GATE.includes(p.kind) && "spec" in p) {
      set({ phase: { kind: "turning-away", spec: p.spec, plate: "plate" in p ? p.plate : undefined } })
    }
  },

  pickSession: (session) => set({ phase: { kind: "to-exit", session } }),

  release: () => {
    const p = get().phase
    if (p.kind === "exit-check") set({ phase: { kind: "exiting", session: p.session } })
  },

  hold: () => {
    const p = get().phase
    if (p.kind === "exit-check") set({ phase: { kind: "back-to-slot", session: p.session } })
  },
}))

/** Session whose vehicle is currently animated or at a gate (hidden from its parking slot). */
export function activeSessionId(phase: Phase): number | null {
  if (phase.kind === "entering") return phase.sessionId
  return "session" in phase ? phase.session.id : null
}

export const isBusy = (phase: Phase) => phase.kind !== "idle"
