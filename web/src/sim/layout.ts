// Geometry of the lot, in metres. x to the right, z towards the camera, y up. Top view:
//
//   z=-10 ┌──────────────── car row (C01..C10) ──────────────────┐
//         │  ▭  ▭  ▭  ▭  ▭  ▭  ▭  ▭  ▭  ▭                         │
//   z=-2  │ ═══════════════ car aisle ═════════════════════════ │
//         │  ▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫  motorbike row (M01..M20)      │
//   z=4.5 │ ═══════════════ main aisle ════════════════════════ │
//   z=7.2 └──┤entry barrier├────────────────────┤exit barrier├──┘
//   z=10.5 ═══════════════════════ road ═══════════════════════════
import type { VehicleType } from "@/lib/parking-api"

export type P2 = [number, number] // (x, z) on the ground

export const LOT = { minX: -16.5, maxX: 16.5, minZ: -10.5, maxZ: 7.2 }
export const ROAD_Z = 10.5
export const ROAD_WIDTH = 4
export const MAIN_AISLE_Z = 4.5
export const CAR_AISLE_Z = -2
export const MOTO_ROW_Z = 2 // motorbike parked position
export const CAR_ROW_Z = -6.6 // car parked position
export const MOTO_SLOT = { width: 1.15, depth: 2.6 }
export const CAR_SLOT = { width: 2.6, depth: 5.2 }

export const ENTRY_X = -14.5
export const EXIT_X = 14.5
export const BARRIER_Z = 7.2
// stops leave room for the longest vehicle (pickup, 5 m) between its nose and the barrier
export const ENTRY_STOP: P2 = [ENTRY_X, 10.0] // outside the barrier, facing the lot
export const EXIT_STOP: P2 = [EXIT_X, 4.6] // inside the barrier, facing the road (just past the main aisle)
export const DISPENSER_POS: P2 = [ENTRY_X - 2.6, 8.6] // ticket box at the driver's side of the entry
export const READER_POS: P2 = [EXIT_X + 2.6, 5.4] // ticket reader at the exit

const ROAD_START: P2 = [-36, ROAD_Z]
const ROAD_END: P2 = [36, ROAD_Z]

/** Ground position of a slot: M01..M20 on one row, C01..C10 on another. */
export function slotPosition(slotId: string): P2 {
  const n = Number(slotId.slice(1)) - 1
  if (slotId.startsWith("M")) return [-10.9 + n * MOTO_SLOT.width, MOTO_ROW_Z]
  return [-11.7 + n * CAR_SLOT.width, CAR_ROW_Z]
}

export function slotType(slotId: string): VehicleType {
  return slotId.startsWith("M") ? "motorbike" : "car"
}

const aisleOf = (type: VehicleType) => (type === "car" ? CAR_AISLE_Z : MAIN_AISLE_Z)

export const paths = {
  /** From the road to the entry barrier. */
  arrive: (): P2[] => [ROAD_START, [ENTRY_X, ROAD_Z], ENTRY_STOP],
  /** Turned away at the entry (driver cancelled): back to the road and away. */
  leaveEntry: (): P2[] => [ENTRY_STOP, [ENTRY_X, ROAD_Z], ROAD_END],
  /** Through the entry barrier to the parking slot. */
  park: (slotId: string): P2[] => {
    const [x, z] = slotPosition(slotId)
    const aisle = aisleOf(slotType(slotId))
    return [ENTRY_STOP, [ENTRY_X, aisle], [x, aisle], [x, z]]
  },
  /** From the slot to the exit barrier. */
  toExit: (slotId: string): P2[] => {
    const [x, z] = slotPosition(slotId)
    const aisle = aisleOf(slotType(slotId))
    return [[x, z], [x, aisle], [EXIT_X, aisle], EXIT_STOP]
  },
  /** Held at the exit by the guard: back to the slot. */
  backToSlot: (slotId: string): P2[] => [...paths.toExit(slotId)].reverse(),
  /** Through the exit barrier and away. */
  leave: (): P2[] => [EXIT_STOP, [EXIT_X, ROAD_Z], ROAD_END],
}
