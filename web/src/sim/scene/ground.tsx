import type { Slot } from "@/lib/parking-api"
import {
  BARRIER_Z,
  CAR_SLOT,
  ENTRY_X,
  EXIT_X,
  LOT,
  MOTO_SLOT,
  ROAD_WIDTH,
  ROAD_Z,
  slotPosition,
} from "@/sim/layout"
import { useTextTexture } from "@/sim/scene/textures"

const ASPHALT = "#4a4744"
const ROAD = "#33312f"

function Flat({ x, z, w, d, color, y = 0.01 }: { x: number; z: number; w: number; d: number; color: string; y?: number }) {
  return (
    <mesh position={[x, y, z]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[w, d]} />
      <meshStandardMaterial color={color} />
    </mesh>
  )
}

function SlotTile({ slot }: { slot: Slot }) {
  const [x, z] = slotPosition(slot.id)
  const size = slot.vehicle_type === "car" ? CAR_SLOT : MOTO_SLOT
  const label = useTextTexture({ lines: [slot.id], width: 128, height: 64, background: "#00000000", color: "#ffffff" })
  const taken = Boolean(slot.session)
  return (
    <group>
      <Flat x={x} z={z} w={size.width - 0.12} d={size.depth} color={taken ? "#8a3a3f" : "#2f6b63"} y={0.015} />
      {/* white lines on both sides */}
      <Flat x={x - size.width / 2} z={z} w={0.08} d={size.depth} color="#ffffff" y={0.02} />
      <Flat x={x + size.width / 2} z={z} w={0.08} d={size.depth} color="#ffffff" y={0.02} />
      <mesh position={[x, 0.025, z - size.depth / 2 + 0.35]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[Math.min(size.width - 0.15, 1.0), 0.5]} />
        <meshBasicMaterial map={label} transparent />
      </mesh>
    </group>
  )
}

/** Road, lot surface, driveways, painted slots and a low fence. */
export function Ground({ slots }: { slots: Slot[] }) {
  const lotW = LOT.maxX - LOT.minX
  const lotD = LOT.maxZ - LOT.minZ
  return (
    <group>
      <Flat x={0} z={0} w={120} d={90} color="#e9dfc8" y={-0.01} />
      <Flat x={0} z={ROAD_Z} w={90} d={ROAD_WIDTH} color={ROAD} />
      {Array.from({ length: 22 }, (_, i) => (
        <Flat key={i} x={-42 + i * 4} z={ROAD_Z} w={2} d={0.15} color="#f5f0e6" y={0.02} />
      ))}
      <Flat x={(LOT.minX + LOT.maxX) / 2} z={(LOT.minZ + LOT.maxZ) / 2} w={lotW} d={lotD} color={ASPHALT} />
      {/* driveways between the lot and the road */}
      {[ENTRY_X, EXIT_X].map((x) => (
        <Flat key={x} x={x} z={(BARRIER_Z + ROAD_Z) / 2} w={3.6} d={ROAD_Z - BARRIER_Z} color={ASPHALT} />
      ))}
      {slots.map((s) => (
        <SlotTile key={s.id} slot={s} />
      ))}
      {/* fence: back and sides of the lot, front with gaps at the gates */}
      <Fence x1={LOT.minX} x2={LOT.maxX} z1={LOT.minZ} z2={LOT.minZ} />
      <Fence x1={LOT.minX} x2={LOT.minX} z1={LOT.minZ} z2={LOT.maxZ} />
      <Fence x1={LOT.maxX} x2={LOT.maxX} z1={LOT.minZ} z2={LOT.maxZ} />
      <Fence x1={ENTRY_X + 1.9} x2={EXIT_X - 1.9} z1={LOT.maxZ} z2={LOT.maxZ} />
    </group>
  )
}

function Fence({ x1, x2, z1, z2 }: { x1: number; x2: number; z1: number; z2: number }) {
  const len = Math.hypot(x2 - x1, z2 - z1)
  return (
    <mesh position={[(x1 + x2) / 2, 0.35, (z1 + z2) / 2]} rotation={[0, Math.atan2(x2 - x1, z2 - z1), 0]}>
      <boxGeometry args={[0.18, 0.7, len]} />
      <meshStandardMaterial color="#ffdc58" />
    </mesh>
  )
}
