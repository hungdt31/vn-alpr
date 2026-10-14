import { Canvas, useFrame } from "@react-three/fiber"
import { useRef, useState } from "react"
import { DicesIcon } from "lucide-react"
import type * as THREE from "three"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { VEHICLE_LABEL, type VehicleType } from "@/lib/parking-api"
import { cn } from "@/lib/utils"
import { Vehicle } from "@/sim/scene/vehicle"
import { useSim } from "@/sim/store"
import { modelsOf, randomSpec, VEHICLE_COLORS, type VehicleSpec } from "@/sim/vehicles"

function Turntable({ spec }: { spec: VehicleSpec }) {
  const ref = useRef<THREE.Group>(null)
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.8
  })
  return (
    <group ref={ref} scale={spec.type === "car" ? 1 : 2.2}>
      <Vehicle spec={spec} plate="" />
    </group>
  )
}

/** Step 0 of an entry: pick the look of the arriving vehicle. */
export function ChooseVehicleDialog() {
  const phase = useSim((s) => s.phase)
  const lot = useSim((s) => s.lot)
  const setPhase = useSim((s) => s.setPhase)
  const cancel = useSim((s) => s.cancelEntry)
  const [spec, setSpec] = useState<VehicleSpec>(randomSpec)

  const setType = (type: VehicleType) => setSpec((s) => ({ ...s, type, model: modelsOf(type)[0].id }))
  const free = lot?.capacity[spec.type].free ?? 0
  const noCard = (lot?.cards.available ?? 0) === 0

  return (
    <Dialog open={phase.kind === "choose"} onOpenChange={(open) => !open && cancel()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-head text-xl">Xe mới tới cổng vào</DialogTitle>
          <DialogDescription>Chọn loại xe, kiểu dáng và màu của xe trong mô phỏng.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="h-56 rounded border-2 bg-accent">
            <Canvas camera={{ position: [4.5, 3.2, 5.5], fov: 40 }} gl={{ preserveDrawingBuffer: true }}>
              <hemisphereLight args={["#ffffff", "#c9bfa8", 1.6]} />
              <directionalLight position={[5, 8, 5]} intensity={1.4} />
              <Turntable spec={spec} />
            </Canvas>
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex gap-2">
              {(["motorbike", "car"] as const).map((t) => (
                <Button key={t} variant={spec.type === t ? "default" : "outline"} onClick={() => setType(t)} className="flex-1">
                  {VEHICLE_LABEL[t]}
                </Button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {modelsOf(spec.type).map((m) => (
                <Button
                  key={m.id}
                  size="sm"
                  variant={spec.model === m.id ? "secondary" : "outline"}
                  onClick={() => setSpec((s) => ({ ...s, model: m.id }))}
                >
                  {m.label}
                </Button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {VEHICLE_COLORS.map((c) => (
                <button
                  key={c.value}
                  type="button"
                  title={c.label}
                  onClick={() => setSpec((s) => ({ ...s, color: c.value }))}
                  className={cn(
                    "size-8 cursor-pointer rounded border-2 transition-transform",
                    spec.color === c.value ? "scale-110 shadow-[3px_3px_0_#000]" : "hover:scale-105",
                  )}
                  style={{ background: c.value }}
                />
              ))}
            </div>
            <p className={cn("text-sm font-medium", free === 0 && "text-destructive")}>
              Còn {free}/{lot?.capacity[spec.type].total ?? 0} chỗ cho {VEHICLE_LABEL[spec.type].toLowerCase()} ·{" "}
              {lot?.cards.available ?? 0} thẻ trong thùng
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setSpec(randomSpec())}>
            <DicesIcon /> Ngẫu nhiên
          </Button>
          <Button disabled={free === 0 || noCard} onClick={() => setPhase({ kind: "arriving", spec })}>
            {free === 0 ? "Bãi đã hết chỗ" : noCard ? "Thùng hết thẻ" : "Cho xe chạy tới cổng"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
