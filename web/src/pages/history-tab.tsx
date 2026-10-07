import { useCallback, useEffect, useState } from "react"
import { SearchIcon } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, formatTime, type GateEvent } from "@/lib/api"

/** Entry/exit log with plate search. `refreshKey` changes when the gate tab logs something. */
export function HistoryTab({ refreshKey }: { refreshKey: number }) {
  const [query, setQuery] = useState("")
  const [rows, setRows] = useState<GateEvent[]>([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async (plate: string) => {
    setLoading(true)
    try {
      setRows(await api.events(plate.trim() || undefined, 200))
    } catch (e) {
      toast.error("Không tải được lịch sử", { description: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load("")
  }, [load, refreshKey])

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          load(query)
        }}
      >
        <Input placeholder="Tìm theo biển số, ví dụ 51G" value={query} onChange={(e) => setQuery(e.target.value)} />
        <Button type="submit" disabled={loading}>
          {loading ? <Spinner /> : <SearchIcon />} Tìm
        </Button>
      </form>

      <EventTable rows={rows} empty={loading ? "Đang tải…" : "Chưa có lượt vào/ra nào."} />
    </div>
  )
}

export function EventTable({ rows, empty }: { rows: GateEvent[]; empty: string }) {
  return (
    <div className="rounded border-2 bg-card shadow-md">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Biển số</TableHead>
            <TableHead>Hướng</TableHead>
            <TableHead>Cổng</TableHead>
            <TableHead>Độ tin cậy</TableHead>
            <TableHead>Thời gian</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                {empty}
              </TableCell>
            </TableRow>
          ) : (
            rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-plate">{r.display}</TableCell>
                <TableCell>
                  {r.direction === "in" ? <Badge>Vào</Badge> : <Badge variant="secondary">Ra</Badge>}
                </TableCell>
                <TableCell>{r.gate}</TableCell>
                <TableCell>{(r.confidence * 100).toFixed(1)}%</TableCell>
                <TableCell>{formatTime(r.created_at)}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  )
}
