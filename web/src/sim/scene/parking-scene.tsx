import { OrbitControls } from "@react-three/drei"
import { Canvas } from "@react-three/fiber"
import { Suspense, useMemo } from "react"

import {
  BARRIER_Z,
  DISPENSER_POS,
  ENTRY_STOP,
  ENTRY_X,
  EXIT_STOP,
  EXIT_X,
  paths,
  READER_POS,
  slotPosition,
  type P2,
} from "@/sim/layout"
import { Ground } from "@/sim/scene/ground"
import { Barrier, Booth, Dispenser, MovingVehicle, Reader, StillVehicle } from "@/sim/scene/props"
import { activeSessionId, useSim, type Phase } from "@/sim/store"
import { specOf, type VehicleSpec } from "@/sim/vehicles"

const FACING_LOT = Math.PI // facing -z
const FACING_ROAD = 0 // facing +z

/** The one vehicle being handled right now: moving, or waiting at a gate. */
function ActiveVehicle({ phase, onDone }: { phase: Phase; onDone: () => void }) {
  const move = useMemo((): { spec: VehicleSpec; plate: string; path?: P2[]; at?: P2; yaw?: number } | null => {
    switch (phase.kind) {
      case "arriving":
        return { spec: phase.spec, plate: "", path: paths.arrive() }
      case "entry-recognize":
        return { spec: phase.spec, plate: "", at: ENTRY_STOP, yaw: FACING_LOT }
      case "entry-card":
      case "entry-confirm":
        return { spec: phase.spec, plate: phase.plate, at: ENTRY_STOP, yaw: FACING_LOT }
      case "entering":
        return { spec: phase.spec, plate: phase.plate, path: paths.park(phase.slotId) }
      case "turning-away":
        return { spec: phase.spec, plate: phase.plate ?? "", path: paths.leaveEntry() }
      case "to-exit":
      case "exiting":
      case "back-to-slot":
      case "exit-check": {
        const s = phase.session
        const spec = specOf(s.vehicle_type, s.vehicle_style)
        if (phase.kind === "exit-check") return { spec, plate: s.display, at: EXIT_STOP, yaw: FACING_ROAD }
        const path =
          phase.kind === "to-exit" ? paths.toExit(s.slot_id) : phase.kind === "exiting" ? paths.leave() : paths.backToSlot(s.slot_id)
        return { spec, plate: s.display, path }
      }
      default:
        return null
    }
  }, [phase])

  if (!move) return null
  if (move.path) {
    return <MovingVehicle key={phase.kind} spec={move.spec} plate={move.plate} path={move.path} onDone={onDone} />
  }
  return <StillVehicle spec={move.spec} plate={move.plate} at={move.at!} yaw={move.yaw!} />
}

export function ParkingScene() {
  const phase = useSim((s) => s.phase)
  const lot = useSim((s) => s.lot)
  const cardPop = useSim((s) => s.cardPop)
  const arrived = useSim((s) => s.arrived)
  const takeCard = useSim((s) => s.takeCard)
  const pickSession = useSim((s) => s.pickSession)

  const activeId = activeSessionId(phase)
  const picking = phase.kind === "exit-pick"
  const slots = lot?.slots ?? []

  return (
    // preserveDrawingBuffer: lets screenshots (and the report) capture the 3D view
    <Canvas camera={{ position: [0, 24, 27], fov: 42 }} dpr={[1, 1.75]} gl={{ preserveDrawingBuffer: true }}>
      <color attach="background" args={["#fff7e8"]} />
      <hemisphereLight args={["#ffffff", "#c9bfa8", 1.4]} />
      <directionalLight position={[12, 20, 10]} intensity={1.6} />
      <Suspense fallback={null}>
        <Ground slots={slots} />
        <Barrier at={[ENTRY_X, BARRIER_Z]} open={phase.kind === "entering"} label="CỔNG VÀO" post="right" />
        <Barrier at={[EXIT_X, BARRIER_Z]} open={phase.kind === "exiting"} label="CỔNG RA" />
        <Booth at={[ENTRY_X + 3.6, BARRIER_Z + 1.6]} />
        <Booth at={[EXIT_X - 3.2, BARRIER_Z + 1.6]} />
        <Dispenser
          at={DISPENSER_POS}
          cards={lot?.cards.available ?? 0}
          active={phase.kind === "entry-card" && Boolean(lot?.cards.next)}
          onTake={takeCard}
          popKey={cardPop}
        />
        <Reader at={READER_POS} active={phase.kind === "exit-check"} />

        {slots.map((slot) => {
          const s = slot.session
          if (!s || s.id === activeId) return null
          return (
            <StillVehicle
              key={s.id}
              spec={specOf(s.vehicle_type, s.vehicle_style)}
              plate={s.display}
              at={slotPosition(slot.id)}
              yaw={FACING_LOT}
              onPick={picking ? () => pickSession(s) : undefined}
            />
          )
        })}

        <ActiveVehicle phase={phase} onDone={arrived} />
      </Suspense>
      <OrbitControls
        target={[0, 0, 0]}
        maxPolarAngle={1.25}
        minDistance={12}
        maxDistance={60}
        enableDamping
        makeDefault
      />
    </Canvas>
  )
}
