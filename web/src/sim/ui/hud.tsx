import { CarFrontIcon, ClockIcon, LogOutIcon, ShieldIcon, TicketIcon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { parkingApi, VEHICLE_LABEL } from "@/lib/parking-api"
import { isBusy, useSim, type Phase } from "@/sim/store"

function hint(phase: Phase): string | null {
  switch (phase.kind) {
    case "arriving":
      return "Xe đang chạy tới cổng vào…"
    case "entry-card":
      return "Bấm vào thùng thẻ (đang nhấp nháy) để lấy thẻ giữ xe"
    case "entering":
      return `Barrier mở · xe đang vào ô ${phase.slotId}`
    case "turning-away":
      return "Xe quay đầu rời cổng vào"
    case "exit-pick":
      return "Chọn xe muốn lấy ra"
    case "to-exit":
      return `Xe ${phase.session.display} đang chạy ra cổng ra…`
    case "exiting":
      return "Barrier mở · xe rời bãi, thẻ về thùng"
    case "back-to-slot":
      return "Bảo vệ giữ xe lại · xe quay về ô đỗ"
    default:
      return null
  }
}

/** Overlays on the 3D scene: lot status, clock, actions and a hint for the current step. */
export function Hud({ onDashboard }: { onDashboard: () => void }) {
  const phase = useSim((s) => s.phase)
  const lot = useSim((s) => s.lot)
  const lotError = useSim((s) => s.lotError)
  const setPhase = useSim((s) => s.setPhase)
  const takeCard = useSim((s) => s.takeCard)
  const refresh = useSim((s) => s.refresh)
  const busy = isBusy(phase)
  const text = hint(phase)

  const travel = async (hours: number) => {
    try {
      await parkingApi.travel(hours)
      await refresh()
      toast(`Tua nhanh ${hours >= 24 ? `${hours / 24} ngày` : `${hours} giờ`}`)
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <div className="pointer-events-none absolute inset-0 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Card size="sm" className="pointer-events-auto w-64">
          <CardContent className="flex flex-col gap-2">
            <p className="font-head">{lot?.name ?? "Bãi giữ xe"}</p>
            {lotError && <p className="text-sm text-destructive">Không kết nối được API: {lotError}</p>}
            {lot &&
              (["motorbike", "car"] as const).map((t) => (
                <div key={t} className="flex flex-col gap-1">
                  <div className="flex justify-between text-sm">
                    <span>{VEHICLE_LABEL[t]}</span>
                    <span className="font-bold">
                      còn {lot.capacity[t].free}/{lot.capacity[t].total}
                    </span>
                  </div>
                  <div className="h-2.5 rounded border-2 bg-muted">
                    <div
                      className="h-full bg-chart-2"
                      style={{ width: `${(100 * lot.capacity[t].free) / lot.capacity[t].total}%` }}
                    />
                  </div>
                </div>
              ))}
            {lot && (
              <p className="flex items-center gap-2 text-sm">
                <TicketIcon className="size-4" /> {lot.cards.available} thẻ trong thùng
                {lot.cards.locked > 0 && <span className="text-destructive">· {lot.cards.locked} bị khoá</span>}
              </p>
            )}
            {lot && (
              <div className="flex flex-col gap-1 border-t-2 pt-2">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <ClockIcon className="size-4" />
                  {new Date(lot.now).toLocaleString("vi-VN")}
                </p>
                {lot.allow_time_travel && (
                  <div className="flex gap-1">
                    {[1, 4, 24].map((h) => (
                      <Button key={h} size="sm" variant="outline" className="flex-1 px-1" onClick={() => travel(h)}>
                        +{h === 24 ? "1 ngày" : `${h}h`}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="pointer-events-auto flex flex-wrap justify-end gap-2">
          <Button size="lg" disabled={busy || !lot} onClick={() => setPhase({ kind: "choose" })}>
            <CarFrontIcon /> Xe tới cổng vào
          </Button>
          <Button size="lg" variant="secondary" disabled={busy || !lot} onClick={() => setPhase({ kind: "exit-pick" })}>
            <LogOutIcon /> Lấy xe ra
          </Button>
          <Button size="lg" variant="outline" onClick={onDashboard}>
            <ShieldIcon /> Bảo vệ
          </Button>
        </div>
      </div>

      {text && (
        <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-3 rounded border-2 bg-primary px-4 py-2 font-head shadow-md">
          {text}
          {phase.kind === "entry-card" && (
            <Button size="sm" variant="secondary" className="pointer-events-auto" onClick={takeCard}>
              <TicketIcon /> Lấy thẻ
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
