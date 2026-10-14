import { useEffect, useState } from "react"

import { ParkingScene } from "@/sim/scene/parking-scene"
import { useSim } from "@/sim/store"
import { ChooseVehicleDialog } from "@/sim/ui/choose-vehicle"
import { Dashboard } from "@/sim/ui/dashboard"
import { EntryConfirmDialog, EntryRecognizeDialog } from "@/sim/ui/entry-dialogs"
import { ExitCheckDialog, ExitPickPanel } from "@/sim/ui/exit-dialogs"
import { Hud } from "@/sim/ui/hud"

/** 3D parking lot: vehicles arrive, get a ticket after plate recognition, park, and leave with the same ticket. */
export function SimulationPage() {
  const refresh = useSim((s) => s.refresh)
  const [dashboard, setDashboard] = useState(false)

  useEffect(() => {
    void refresh()
  }, [refresh])

  return (
    <div className="relative min-h-0 flex-1 overflow-hidden">
      <ParkingScene />
      <Hud onDashboard={() => setDashboard(true)} />
      <ExitPickPanel />
      <ChooseVehicleDialog />
      <EntryRecognizeDialog />
      <EntryConfirmDialog />
      <ExitCheckDialog />
      <Dashboard open={dashboard} onOpenChange={setDashboard} />
    </div>
  )
}
