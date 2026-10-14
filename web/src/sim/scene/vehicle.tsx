import { Edges } from "@react-three/drei"
import type { ThreeEvent } from "@react-three/fiber"
import { useState } from "react"

import { plateLines, useTextTexture } from "@/sim/scene/textures"
import type { VehicleSpec } from "@/sim/vehicles"

// All vehicles face +z in their own frame; movers rotate the group around y.
const INK = "#000000"
const GLASS = "#5d7e99"
const TYRE = "#1f1f1f"

type V3 = [number, number, number]

function Part({ size, position, color, edges = true }: { size: V3; position: V3; color: string; edges?: boolean }) {
  return (
    <mesh position={position} castShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} flatShading />
      {edges && <Edges color={INK} threshold={20} />}
    </mesh>
  )
}

function Wheel({ position, radius, width }: { position: V3; radius: number; width: number }) {
  return (
    <mesh position={position} rotation={[0, 0, Math.PI / 2]}>
      <cylinderGeometry args={[radius, radius, width, 14]} />
      <meshStandardMaterial color={TYRE} flatShading />
      <Edges color="#555" threshold={30} />
    </mesh>
  )
}

function Plate({ display, twoLine, position, rotationY, size }: {
  display: string
  twoLine: boolean
  position: V3
  rotationY: number
  size: [number, number]
}) {
  const texture = useTextTexture({
    lines: plateLines(display, twoLine),
    width: twoLine ? 256 : 512,
    height: twoLine ? 192 : 112,
    border: "#000",
  })
  return (
    <mesh position={position} rotation={[0, rotationY, 0]}>
      <planeGeometry args={size} />
      <meshBasicMaterial map={texture} toneMapped={false} />
    </mesh>
  )
}

const CARS: Record<string, { body: V3; bodyY: number; cabin: V3; cabinY: number; cabinZ: number; wheelZ: number }> = {
  sedan: { body: [1.8, 0.62, 4.4], bodyY: 0.62, cabin: [1.6, 0.55, 2.2], cabinY: 1.2, cabinZ: -0.2, wheelZ: 1.35 },
  suv: { body: [1.9, 0.85, 4.6], bodyY: 0.78, cabin: [1.8, 0.72, 2.8], cabinY: 1.56, cabinZ: -0.35, wheelZ: 1.45 },
  hatchback: { body: [1.7, 0.62, 3.8], bodyY: 0.6, cabin: [1.58, 0.6, 2.0], cabinY: 1.2, cabinZ: -0.45, wheelZ: 1.2 },
  pickup: { body: [1.9, 0.75, 5.0], bodyY: 0.72, cabin: [1.8, 0.75, 1.9], cabinY: 1.47, cabinZ: 0.75, wheelZ: 1.6 },
}

function Car({ spec, plate }: { spec: VehicleSpec; plate: string }) {
  const c = CARS[spec.model] ?? CARS.sedan
  const half = c.body[2] / 2
  const plateY = c.bodyY - 0.05
  return (
    <group>
      <Part size={c.body} position={[0, c.bodyY, 0]} color={spec.color} />
      <Part size={c.cabin} position={[0, c.cabinY, c.cabinZ]} color={GLASS} />
      {spec.model === "pickup" && (
        <Part size={[1.9, 0.35, 2.3]} position={[0, c.bodyY + 0.55, -1.25]} color={spec.color} />
      )}
      {[-1, 1].map((sx) =>
        [-1, 1].map((sz) => (
          <Wheel key={`${sx}${sz}`} position={[sx * (c.body[0] / 2 - 0.05), 0.36, sz * c.wheelZ]} radius={0.36} width={0.3} />
        )),
      )}
      {/* headlights */}
      {[-0.6, 0.6].map((x) => (
        <Part key={x} size={[0.36, 0.14, 0.04]} position={[x, c.bodyY + 0.12, half + 0.01]} color="#fff7c2" />
      ))}
      <Plate display={plate} twoLine={false} position={[0, plateY, half + 0.025]} rotationY={0} size={[0.86, 0.19]} />
      <Plate display={plate} twoLine={false} position={[0, plateY, -half - 0.025]} rotationY={Math.PI} size={[0.86, 0.19]} />
    </group>
  )
}

function Motorbike({ spec, plate }: { spec: VehicleSpec; plate: string }) {
  const sport = spec.model === "sport"
  const scooter = spec.model === "scooter"
  return (
    <group>
      <Wheel position={[0, 0.3, 0.68]} radius={0.3} width={0.13} />
      <Wheel position={[0, 0.3, -0.68]} radius={0.3} width={0.13} />
      {scooter ? (
        <>
          <Part size={[0.46, 0.42, 1.25]} position={[0, 0.56, -0.12]} color={spec.color} />
          <Part size={[0.46, 0.85, 0.22]} position={[0, 0.78, 0.55]} color={spec.color} />
        </>
      ) : (
        <>
          <Part size={[0.22, 0.24, 1.3]} position={[0, 0.55, 0]} color="#333" />
          <Part size={[0.42, sport ? 0.34 : 0.26, sport ? 0.62 : 0.5]} position={[0, sport ? 0.86 : 0.78, 0.25]} color={spec.color} />
          <Part size={[0.36, 0.3, 0.55]} position={[0, 0.66, -0.42]} color={spec.color} />
        </>
      )}
      {/* seat */}
      <Part size={[0.36, 0.12, 0.72]} position={[0, scooter ? 0.83 : 0.9, -0.28]} color="#1a1a1a" />
      {/* fork and handlebar */}
      <Part size={[0.08, 0.7, 0.08]} position={[0, 0.72, 0.68]} color="#777" edges={false} />
      <Part size={[0.74, 0.06, 0.06]} position={[0, 1.12, 0.6]} color="#222" />
      <Part size={[0.22, 0.14, 0.06]} position={[0, 1.02, 0.74]} color="#fff7c2" />
      {/* 2-line plate on the rear */}
      <Plate display={plate} twoLine position={[0, 0.66, -0.73]} rotationY={Math.PI} size={[0.42, 0.32]} />
    </group>
  )
}

interface VehicleProps {
  spec: VehicleSpec
  plate: string
  /** clickable (picking the vehicle to take out) */
  onPick?: () => void
}

export function Vehicle({ spec, plate, onPick }: VehicleProps) {
  const [hover, setHover] = useState(false)
  const pick = onPick
    ? {
        onClick: (e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation()
          onPick()
        },
        onPointerOver: (e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation()
          setHover(true)
          document.body.style.cursor = "pointer"
        },
        onPointerOut: () => {
          setHover(false)
          document.body.style.cursor = ""
        },
      }
    : {}
  const isCar = spec.type === "car"
  return (
    <group {...pick} scale={hover ? 1.08 : 1}>
      {onPick && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
          <planeGeometry args={isCar ? [2.3, 4.9] : [0.95, 2.2]} />
          <meshBasicMaterial color={hover ? "#ffdc58" : "#ffe7a3"} transparent opacity={hover ? 0.95 : 0.55} />
        </mesh>
      )}
      {isCar ? <Car spec={spec} plate={plate} /> : <Motorbike spec={spec} plate={plate} />}
    </group>
  )
}
