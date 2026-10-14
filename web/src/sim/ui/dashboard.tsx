import { useCallback, useEffect, useState } from "react"
// DownloadIcon: used by the training data export section, temporarily hidden below
import { /* DownloadIcon, */ RefreshCwIcon, UnlockIcon } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatTime } from "@/lib/api"
import { formatVnd, parkingApi, VEHICLE_LABEL, type Session, type Stats } from "@/lib/parking-api"
import { useSim } from "@/sim/store"

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded border-2 bg-card p-3 shadow-[2px_2px_0_#000]">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="font-plate text-2xl">{value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  )
}

const MATCH_LABEL = { ok: "khớp", suspect: "nghi đọc sai", mismatch: "không khớp" } as const

/** Guard's view: today's numbers, model accuracy in the field, locked tickets, recent visits, data export. */
export function Dashboard({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const lot = useSim((s) => s.lot)
  const refreshLot = useSim((s) => s.refresh)
  const [stats, setStats] = useState<Stats | null>(null)
  const [sessions, setSessions] = useState<Session[]>([])

  const load = useCallback(async () => {
    try {
      const [st, ss] = await Promise.all([parkingApi.stats(), parkingApi.sessions(undefined, 40)])
      setStats(st)
      setSessions(ss)
    } catch (e) {
      toast.error("Không tải được số liệu", { description: (e as Error).message })
    }
  }, [])

  useEffect(() => {
    if (open) void load()
  }, [open, load])

  const restore = async (cardId: number) => {
    await parkingApi.restoreCard(cardId)
    toast.success(`Thẻ T${String(cardId).padStart(3, "0")} đã về thùng`)
    await Promise.all([refreshLot(), load()])
  }

  // Training data export: temporarily hidden (see the commented section in the JSX below)
  // const exportData = async (editedOnly: boolean) => {
  //   try {
  //     const r = await parkingApi.exportCorrections(editedOnly)
  //     toast.success(`Đã xuất ${r.lines} ảnh dòng chữ`, { description: `${r.out} · thêm vào train_dirs của configs/crnn.yaml` })
  //   } catch (e) {
  //     toast.error("Xuất dữ liệu thất bại", { description: (e as Error).message })
  //   }
  // }

  const rate = stats?.ocr_edit_rate
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle className="font-head text-xl">Bảng điều khiển bảo vệ</SheetTitle>
          <SheetDescription>Số liệu hôm nay theo đồng hồ mô phỏng.</SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-5 px-4 pb-6">
          <Button variant="outline" size="sm" className="w-fit" onClick={load}>
            <RefreshCwIcon /> Làm mới
          </Button>

          {stats && (
            <div className="grid grid-cols-2 gap-3">
              <Tile label="Xe máy trong bãi" value={String(stats.parked.motorbike ?? 0)} />
              <Tile label="Ô tô trong bãi" value={String(stats.parked.car ?? 0)} />
              <Tile label="Doanh thu hôm nay" value={formatVnd(stats.today.revenue)} sub={`tổng ${formatVnd(stats.revenue_total)}`} />
              <Tile label="Lượt vào / ra hôm nay" value={`${stats.today.entries} / ${stats.today.exits}`} />
              <Tile
                label="Tỷ lệ phải sửa tay biển số"
                value={rate == null ? "—" : `${(rate * 100).toFixed(0)}%`}
                sub={`${stats.corrections} lần sửa · ước lượng lỗi của model`}
              />
              <Tile label="Bảo vệ duyệt tay" value={String(stats.overrides)} sub={`${stats.lost_cards} thẻ đang khoá`} />
            </div>
          )}

          {lot && (
            <section className="flex flex-col gap-2">
              <h3 className="font-head">Bảng giá</h3>
              <Table className="rounded border-2 bg-card">
                <TableHeader>
                  <TableRow>
                    <TableHead>Loại xe</TableHead>
                    <TableHead>Giá cơ bản</TableHead>
                    <TableHead>Sau đó</TableHead>
                    <TableHead>Mất thẻ</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(["motorbike", "car"] as const).map((t) => (
                    <TableRow key={t}>
                      <TableCell>{VEHICLE_LABEL[t]}</TableCell>
                      <TableCell>
                        {formatVnd(lot.fees[t].base)} / {lot.fees[t].base_hours} giờ đầu
                      </TableCell>
                      <TableCell>{formatVnd(lot.fees[t].per_hour)}/giờ</TableCell>
                      <TableCell>{formatVnd(lot.fees[t].lost_card)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </section>
          )}

          {lot && lot.cards.locked_ids.length > 0 && (
            <section className="flex flex-col gap-2">
              <h3 className="font-head">Thẻ bị khoá (báo mất)</h3>
              <div className="flex flex-wrap gap-2">
                {lot.cards.locked_ids.map((id) => (
                  <Button key={id} size="sm" variant="outline" onClick={() => restore(id)}>
                    <UnlockIcon /> T{String(id).padStart(3, "0")} · tìm thấy, trả về thùng
                  </Button>
                ))}
              </div>
            </section>
          )}

          {/* Training data export: temporarily hidden
          <section className="flex flex-col gap-2">
            <h3 className="font-head">Dữ liệu huấn luyện từ cổng vào</h3>
            <p className="text-sm text-muted-foreground">
              Mỗi lần người gửi sửa biển số là một nhãn đúng cho model. Xuất ra dạng ảnh dòng chữ + labels.tsv để fine-tune
              CRNN.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => exportData(true)}>
                <DownloadIcon /> Xuất các biển đã sửa tay
              </Button>
              <Button size="sm" variant="outline" onClick={() => exportData(false)}>
                Xuất tất cả biển đã xác nhận
              </Button>
            </div>
          </section>
          */}

          <section className="flex flex-col gap-2">
            <h3 className="font-head">Lượt gửi gần đây</h3>
            <div className="overflow-x-auto rounded border-2 bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Thẻ</TableHead>
                    <TableHead>Biển số</TableHead>
                    <TableHead>Vào</TableHead>
                    <TableHead>Ra</TableHead>
                    <TableHead>Phí</TableHead>
                    <TableHead>Ghi chú</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sessions.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell className="font-plate">{s.card_code}</TableCell>
                      <TableCell>
                        <span className="font-plate">{s.display}</span>
                        {s.edited && (
                          <span className="block text-xs text-muted-foreground">model đọc: {s.plate_ocr || "—"}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs">{formatTime(s.entry_time)}</TableCell>
                      <TableCell className="text-xs">{s.exit_time ? formatTime(s.exit_time) : <Badge>đang gửi</Badge>}</TableCell>
                      <TableCell>{s.fee != null ? formatVnd(s.fee) : "—"}</TableCell>
                      <TableCell className="max-w-48 text-xs">
                        {s.edited && <Badge variant="secondary">sửa tay</Badge>}{" "}
                        {s.lost_card && <Badge variant="destructive">mất thẻ</Badge>}{" "}
                        {s.exit_match && s.exit_match !== "ok" && (
                          <Badge variant="outline">{MATCH_LABEL[s.exit_match]}</Badge>
                        )}
                        {s.override_reason && <span className="mt-1 block">BV: {s.override_reason}</span>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </section>
        </div>
      </SheetContent>
    </Sheet>
  )
}
