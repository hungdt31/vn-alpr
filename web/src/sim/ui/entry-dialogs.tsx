import { useEffect, useState } from "react"
import { CheckIcon, PencilIcon, TicketIcon, TriangleAlertIcon } from "lucide-react"
import { toast } from "sonner"

import { PlateImage } from "@/components/plate-image"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import type { PlateResult } from "@/lib/api"
import { formatVnd, parkingApi, VEHICLE_LABEL, type Capture } from "@/lib/parking-api"
import { useSim } from "@/sim/store"
import { PhotoInput } from "@/sim/ui/photo-input"

/** The model's best guess: a valid plate first, then the most confident detection. */
function bestRead(plates: PlateResult[]): PlateResult | null {
  if (!plates.length) return null
  return [...plates].sort((a, b) => Number(b.valid) - Number(a.valid) || b.det_conf - a.det_conf)[0]
}

/** Live check of a typed plate with the server's VN plate rules (same code as the pipeline). */
function usePlateCheck(text: string) {
  const [check, setCheck] = useState<{ text: string; valid: boolean; display: string; normalized: string } | null>(null)
  useEffect(() => {
    if (!text.trim()) return
    const t = setTimeout(() => {
      parkingApi
        .validate(text)
        .then((r) => setCheck({ text, valid: r.valid, display: r.display, normalized: r.text }))
        .catch(() => setCheck(null))
    }, 250)
    return () => clearTimeout(t)
  }, [text])
  return check?.text === text ? check : null // ignore answers for an older text
}

/** Step 1 of an entry: photo at the gate, model reads the plate, the driver may correct it. */
export function EntryRecognizeDialog() {
  const phase = useSim((s) => s.phase)
  const lot = useSim((s) => s.lot)
  const setPhase = useSim((s) => s.setPhase)
  const cancel = useSim((s) => s.cancelEntry)
  const open = phase.kind === "entry-recognize"

  const [capture, setCapture] = useState<Capture | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [plate, setPlate] = useState("")
  const [loading, setLoading] = useState(false)
  const check = usePlateCheck(plate)

  // fresh form for each vehicle
  useEffect(() => {
    if (!open) {
      setCapture(null)
      setPreview(null)
      setPlate("")
    }
  }, [open])

  const run = async (file: File) => {
    setPreview(URL.createObjectURL(file))
    setLoading(true)
    try {
      const { capture } = await parkingApi.capture(file)
      setCapture(capture)
      setPlate(bestRead(capture.plates)?.display ?? "")
    } catch (e) {
      toast.error("Không nhận diện được", { description: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }

  if (phase.kind !== "entry-recognize" && phase.kind !== "arriving") return null
  const read = capture ? bestRead(capture.plates) : null
  const edited = Boolean(check?.valid && read && check.normalized !== read.text)
  const parkedAlready = check?.valid
    ? lot?.slots.find((s) => s.session?.plate === check.normalized)?.session
    : undefined
  const canContinue = Boolean(capture && check?.valid && !parkedAlready)

  return (
    <Dialog open={open} onOpenChange={(o) => !o && cancel()} disablePointerDismissal>
      <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="font-head text-xl">Cổng vào · Nhận diện biển số</DialogTitle>
          <DialogDescription>
            {phase.kind === "entry-recognize" &&
              `${VEHICLE_LABEL[phase.spec.type]} đang chờ trước barrier. Chụp hoặc tải ảnh biển số xe lên.`}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 md:grid-cols-[3fr_2fr]">
          <div>
            {preview ? (
              <div className="flex flex-col gap-2">
                <PlateImage src={preview} plates={capture?.plates ?? []} />
                <Button variant="outline" size="sm" className="w-fit" onClick={() => setPreview(null)} disabled={loading}>
                  Chụp lại
                </Button>
              </div>
            ) : (
              <PhotoInput onFile={run} disabled={loading} />
            )}
          </div>

          <div className="flex flex-col gap-3">
            {loading && (
              <p className="flex items-center gap-2 font-medium">
                <Spinner /> Đang nhận diện…
              </p>
            )}
            {capture && (
              <>
                <div className="rounded border-2 bg-muted p-3 text-sm">
                  <p className="text-muted-foreground">Model đọc được</p>
                  <p className="font-plate text-xl">{read ? read.display || read.text || "?" : "Không thấy biển số"}</p>
                  {read && <p className="text-muted-foreground">Độ tin cậy OCR {(read.ocr_conf * 100).toFixed(0)}%</p>}
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="plate" className="flex items-center gap-2">
                    <PencilIcon className="size-4" /> Biển số (sửa nếu chưa đúng)
                  </Label>
                  <Input
                    id="plate"
                    value={plate}
                    onChange={(e) => setPlate(e.target.value)}
                    placeholder="VD: 59-X1 123.45 hoặc 51G-123.45"
                    className="font-plate text-lg"
                  />
                  {plate.trim() && check && (
                    <p className={check.valid ? "text-sm text-green-800" : "text-sm text-destructive"}>
                      {check.valid ? `✅ Hợp lệ: ${check.display}` : "⚠️ Chưa đúng định dạng biển số Việt Nam"}
                    </p>
                  )}
                  {edited && <Badge variant="secondary">Đã sửa tay · sẽ dùng làm dữ liệu huấn luyện</Badge>}
                  {parkedAlready && (
                    <p className="flex items-center gap-2 rounded border-2 bg-red-100 p-2 text-sm">
                      <TriangleAlertIcon className="size-4 shrink-0" />
                      Xe {parkedAlready.display} đang ở ô {parkedAlready.slot_id} (thẻ {parkedAlready.card_code}), không thể gửi
                      thêm lần nữa.
                    </p>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={cancel}>
            Huỷ · xe quay đầu
          </Button>
          <Button
            disabled={!canContinue}
            onClick={() => {
              if (phase.kind === "entry-recognize" && capture) {
                setPhase({ kind: "entry-card", spec: phase.spec, capture, plate: check?.display ?? plate })
              }
            }}
          >
            <TicketIcon /> Tiếp: lấy thẻ
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Step 3 of an entry: the ticket is out of the dispenser, confirm to open the barrier. */
export function EntryConfirmDialog() {
  const phase = useSim((s) => s.phase)
  const lot = useSim((s) => s.lot)
  const confirm = useSim((s) => s.confirmEntry)
  const cancel = useSim((s) => s.cancelEntry)
  const [busy, setBusy] = useState(false)
  if (phase.kind !== "entry-confirm") return null
  const fee = lot?.fees[phase.spec.type]

  const submit = async () => {
    setBusy(true)
    try {
      const s = await confirm()
      toast.success(`Mời xe vào ô ${s.slot_id}`, { description: `${s.display} · thẻ ${s.card_code}` })
    } catch (e) {
      toast.error("Không gửi được xe", { description: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && cancel()} disablePointerDismissal>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-head text-xl">Xác nhận gửi xe</DialogTitle>
          <DialogDescription>Giữ thẻ cẩn thận: khi lấy xe phải trả đúng thẻ này.</DialogDescription>
        </DialogHeader>
        <div className="relative rotate-[-2deg] rounded border-2 bg-primary p-4 shadow-[6px_6px_0_#000]">
          <p className="text-xs font-bold tracking-widest">THẺ GIỮ XE · {lot?.name}</p>
          <p className="font-plate text-5xl">{phase.cardCode}</p>
          <div className="mt-2 flex items-end justify-between gap-2">
            <div>
              <p className="font-plate text-xl">{phase.plate}</p>
              <p className="text-sm font-medium">
                {VEHICLE_LABEL[phase.spec.type]} · vào lúc {lot ? new Date(lot.now).toLocaleTimeString("vi-VN") : ""}
              </p>
            </div>
            <TicketIcon className="size-10" />
          </div>
        </div>
        {fee && (
          <p className="text-sm">
            Giá: <b>{formatVnd(fee.base)}</b> cho {fee.base_hours} giờ đầu, sau đó <b>{formatVnd(fee.per_hour)}</b>/giờ. Mất
            thẻ phạt {formatVnd(fee.lost_card)}.
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={cancel} disabled={busy}>
            Huỷ
          </Button>
          <Button onClick={submit} disabled={busy}>
            {busy ? <Spinner /> : <CheckIcon />} Xác nhận · mở barrier
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
