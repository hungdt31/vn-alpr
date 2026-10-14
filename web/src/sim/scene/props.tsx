import { Billboard, Edges } from "@react-three/drei"
import { useFrame } from "@react-three/fiber"
import { useEffect, useRef } from "react"
import * as THREE from "three"

import type { P2 } from "@/sim/layout"
import { useTextTexture } from "@/sim/scene/textures"
import { Vehicle } from "@/sim/scene/vehicle"
import type { VehicleSpec } from "@/sim/vehicles"

/** Yaw that turns a model facing +z towards (dx, dz). */
export const yawOf = (dx: number, dz: number) => Math.atan2(dx, dz)

function lerpAngle(a: number, b: number, t: number) {
  const d = Math.atan2(Math.sin(b - a), Math.cos(b - a))
  return a + d * t
}

/** Drives a vehicle along a polyline at constant speed, turning smoothly; calls onDone once at the end. */
export function MovingVehicle({ spec, plate, path, speed = 8, onDone }: {
  spec: VehicleSpec
  plate: string
  path: P2[]
  speed?: number
  onDone: () => void
}) {
  const ref = useRef<THREE.Group>(null)
  const state = useRef({ seg: 0, t: 0, done: false })
  const doneRef = useRef(onDone)
  useEffect(() => {
    doneRef.current = onDone
  }, [onDone])

  useEffect(() => {
    const g = ref.current
    if (!g || path.length < 2) return
    g.position.set(path[0][0], 0, path[0][1])
    g.rotation.y = yawOf(path[1][0] - path[0][0], path[1][1] - path[0][1])
    state.current = { seg: 0, t: 0, done: false }
  }, [path])

  useFrame((_, delta) => {
    const g = ref.current
    const s = state.current
    if (!g || s.done || path.length < 2) return
    let move = Math.min(delta, 0.05) * speed
    while (move > 0 && s.seg < path.length - 1) {
      const [ax, az] = path[s.seg]
      const [bx, bz] = path[s.seg + 1]
      const len = Math.hypot(bx - ax, bz - az) || 1e-6
      const left = len * (1 - s.t)
      if (move < left) {
        s.t += move / len
        move = 0
      } else {
        move -= left
        s.seg += 1
        s.t = 0
      }
    }
    const i = Math.min(s.seg, path.length - 2)
    const [ax, az] = path[i]
    const [bx, bz] = path[i + 1]
    const t = s.seg >= path.length - 1 ? 1 : s.t
    g.position.set(ax + (bx - ax) * t, 0, az + (bz - az) * t)
    g.rotation.y = lerpAngle(g.rotation.y, yawOf(bx - ax, bz - az), Math.min(1, delta * 6))
    if (s.seg >= path.length - 1) {
      s.done = true
      doneRef.current()
    }
  })

  return (
    <group ref={ref}>
      <Vehicle spec={spec} plate={plate} />
    </group>
  )
}

/** A vehicle standing still at (x, z), facing yaw. */
export function StillVehicle({ spec, plate, at, yaw, onPick }: {
  spec: VehicleSpec
  plate: string
  at: P2
  yaw: number
  onPick?: () => void
}) {
  return (
    <group position={[at[0], 0, at[1]]} rotation={[0, yaw, 0]}>
      <Vehicle spec={spec} plate={plate} onPick={onPick} />
    </group>
  )
}

/** Boom barrier across a driveway; the arm swings up when open. `post` is the side the pillar stands on. */
export function Barrier({ at, open, label, post = "left" }: { at: P2; open: boolean; label: string; post?: "left" | "right" }) {
  const arm = useRef<THREE.Group>(null)
  useFrame((_, delta) => {
    if (!arm.current) return
    const target = open ? 1.4 : 0
    arm.current.rotation.z = THREE.MathUtils.damp(arm.current.rotation.z, target, 4, delta)
  })
  const [x, z] = at
  const right = post === "right"
  return (
    // a right-hand pillar is the left one turned around, so its arm points back across the driveway
    <group position={[x + (right ? 2.1 : -2.1), 0, z]} rotation={[0, right ? Math.PI : 0, 0]}>
      <mesh position={[0, 0.55, 0]}>
        <boxGeometry args={[0.45, 1.1, 0.45]} />
        <meshStandardMaterial color="#ffdc58" />
        <Edges color="#000" />
      </mesh>
      <group ref={arm} position={[0, 1.0, 0]}>
        {[0, 1, 2, 3].map((i) => (
          <mesh key={i} position={[0.55 + i * 0.95, 0, 0]}>
            <boxGeometry args={[0.95, 0.14, 0.14]} />
            <meshStandardMaterial color={i % 2 ? "#ffffff" : "#e63946"} />
            <Edges color="#000" />
          </mesh>
        ))}
      </group>
      <Sign text={label} position={[0, 2.3, 0]} />
    </group>
  )
}

/**
 * A label in the scene that always faces the camera. Drawn on a texture rather than with drei's <Html>:
 * under React StrictMode the first <Html> of the scene never got mounted.
 */
export function Sign({ text, position, background = "#ffffff" }: {
  text: string
  position: [number, number, number]
  background?: string
}) {
  const texture = useTextTexture({
    lines: [text],
    width: 320,
    height: 96,
    background,
    border: "#000",
    font: '"Be Vietnam Pro", "Arial Black", sans-serif',
  })
  return (
    <Billboard position={position}>
      <mesh>
        <planeGeometry args={[2.4, 0.72]} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
    </Billboard>
  )
}

/** Guard booth next to a gate. */
export function Booth({ at }: { at: P2 }) {
  return (
    <group position={[at[0], 0, at[1]]}>
      <mesh position={[0, 1.1, 0]}>
        <boxGeometry args={[1.6, 2.2, 1.6]} />
        <meshStandardMaterial color="#f5f0e6" />
        <Edges color="#000" />
      </mesh>
      <mesh position={[0, 2.3, 0]}>
        <boxGeometry args={[2.0, 0.2, 2.0]} />
        <meshStandardMaterial color="#e63946" />
        <Edges color="#000" />
      </mesh>
      <mesh position={[0, 1.4, 0.81]}>
        <planeGeometry args={[1.1, 0.7]} />
        <meshStandardMaterial color="#5d7e99" />
      </mesh>
    </group>
  )
}

/** Ticket dispenser: a stack of cards on top shows how many are left; clickable when a card can be taken. */
export function Dispenser({ at, cards, active, onTake, popKey }: {
  at: P2
  cards: number
  active: boolean
  onTake: () => void
  popKey: number
}) {
  const body = useRef<THREE.Mesh>(null)
  const prompt = useRef<THREE.Group>(null)
  useFrame(({ clock }) => {
    const bounce = Math.abs(Math.sin(clock.elapsedTime * 4))
    if (body.current) body.current.position.y = 0.75 + (active ? bounce * 0.12 : 0)
    if (prompt.current) prompt.current.position.y = 3.3 + bounce * 0.3
  })
  const visible = Math.min(cards, 12)
  return (
    <group
      position={[at[0], 0, at[1]]}
      onClick={(e) => {
        e.stopPropagation()
        if (active) onTake()
      }}
      onPointerOver={() => {
        if (active) document.body.style.cursor = "pointer"
      }}
      onPointerOut={() => {
        document.body.style.cursor = ""
      }}
    >
      <mesh position={[0, 0.25, 0]}>
        <boxGeometry args={[0.2, 0.5, 0.2]} />
        <meshStandardMaterial color="#333" />
      </mesh>
      <mesh ref={body} position={[0, 0.75, 0]}>
        <boxGeometry args={[0.8, 0.9, 0.6]} />
        <meshStandardMaterial color={active ? "#ffdc58" : "#2a9d8f"} emissive={active ? "#ffdc58" : "#000"} emissiveIntensity={active ? 0.25 : 0} />
        <Edges color="#000" />
      </mesh>
      {Array.from({ length: visible }, (_, i) => (
        <mesh key={i} position={[0, 1.24 + i * 0.035, 0]}>
          <boxGeometry args={[0.54, 0.025, 0.34]} />
          <meshStandardMaterial color={i % 2 ? "#ffffff" : "#ffe7a3"} />
        </mesh>
      ))}
      <PoppingCard key={popKey} play={popKey > 0} />
      <Sign text={`Thùng thẻ: ${cards}`} position={[0, 2.1, 0]} />
      {active && (
        <group ref={prompt} position={[0, 3.3, 0]}>
          <Sign text="BẤM ĐỂ LẤY THẺ" position={[0, 0, 0]} background="#ffdc58" />
        </group>
      )}
    </group>
  )
}

/** A ticket flying out of the dispenser (replayed by remounting with a new key). */
function PoppingCard({ play }: { play: boolean }) {
  const ref = useRef<THREE.Mesh>(null)
  const t = useRef(0)
  useFrame((_, delta) => {
    const m = ref.current
    if (!m || !play) return
    t.current += delta
    const k = Math.min(1, t.current / 1.2)
    m.visible = k < 1
    m.position.set(k * 1.6, 1.3 + Math.sin(k * Math.PI) * 1.4, k * 0.4)
    m.rotation.set(k * Math.PI * 2, k * Math.PI, 0)
  })
  return (
    <mesh ref={ref} visible={false}>
      <boxGeometry args={[0.54, 0.03, 0.34]} />
      <meshStandardMaterial color="#ffdc58" />
      <Edges color="#000" />
    </mesh>
  )
}

/** Exit ticket reader. */
export function Reader({ at, active }: { at: P2; active: boolean }) {
  return (
    <group position={[at[0], 0, at[1]]}>
      <mesh position={[0, 0.55, 0]}>
        <boxGeometry args={[0.2, 1.1, 0.2]} />
        <meshStandardMaterial color="#333" />
      </mesh>
      <mesh position={[0, 1.25, 0]}>
        <boxGeometry args={[0.7, 0.6, 0.35]} />
        <meshStandardMaterial color={active ? "#ffdc58" : "#457b9d"} />
        <Edges color="#000" />
      </mesh>
    </group>
  )
}
