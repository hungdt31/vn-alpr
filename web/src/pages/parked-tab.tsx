import { useEffect, useState } from "react"
import { RefreshCwIcon } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, formatDuration, formatTime, type GateEvent } from "@/lib/api"

/** Vehicles whose latest event is an entry, with how long they have been parked. */
export function ParkedTab({ refreshKey }: { refreshKey: number }) {
  const [rows, setRows] = useState<GateEvent[]>([])
  const [now, setNow] = useState(() => Date.now())

  const load = async () => {
    try {
      setRows(await api.parked())
      setNow(Date.now())
    } catch (e) {
      toast.error("Không tải được danh sách xe", { description: (e as Error).message })
    }
  }

  useEffect(() => {
    load()
  }, [refreshKey])

  // keep "time parked" ticking without refetching
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="font-head text-xl">
          <Badge className="me-2 text-base">{rows.length}</Badge>
          xe đang trong bãi
        </p>
        <Button variant="outline" onClick={load}>
          <RefreshCwIcon /> Làm mới
        </Button>
      </div>
      <div className="rounded border-2 bg-card shadow-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Biển số</TableHead>
              <TableHead>Cổng vào</TableHead>
              <TableHead>Giờ vào</TableHead>
              <TableHead>Đã gửi</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-muted-foreground">
                  Bãi đang trống.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-plate">{r.display}</TableCell>
                  <TableCell>{r.gate}</TableCell>
                  <TableCell>{formatTime(r.created_at)}</TableCell>
                  <TableCell>
                    {formatDuration(Math.max(0, Math.round((now - new Date(r.created_at).getTime()) / 1000)))}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
