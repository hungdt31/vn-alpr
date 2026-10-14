import { useEffect, useMemo, useState } from "react"
import { CarFrontIcon, HandIcon, ScanSearchIcon, ShieldCheckIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import { PlateImage } from "@/components/plate-image"
import { formatDuration } from "@/lib/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { formatVnd, parkingApi, VEHICLE_LABEL, type Capture, type ExitCheck, type Session } from "@/lib/parking-api"
import { useSim } from "@/sim/store"
import { PhotoInput } from "@/sim/ui/photo-input"

/** Floating panel while picking which parked vehicle leaves (the 3D vehicles are clickable too). */
export function ExitPickPanel() {
  const phase = useSim((s) => s.phase)
  const lot = useSim((s) => s.lot)
  const pick = useSim((s) => s.pickSession)
  const setPhase = useSim((s) => s.setPhase)
  const [query, setQuery] = useState("")
  const parked = useMemo(() => (lot?.slots ?? []).flatMap((s) => (s.session ? [s.session] : [])), [lot])
  if (phase.kind !== "exit-pick") return null
  const q = query.replace(/[^0-9a-z]/gi, "").toUpperCase()
  const shown = parked.filter((s) => s.plate.includes(q))

  return (
    <Card className="pointer-events-auto absolute top-4 right-4 bottom-4 w-80 max-w-[calc(100%-2rem)]">
      <CardHeader>
        <CardTitle className="font-head text-lg">Lấy xe ra</CardTitle>
        <p className="text-sm text-muted-foreground">Bấm vào xe trong bãi (ô vàng), hoặc chọn trong danh sách.</p>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
        <Input placeholder="Tìm biển số…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
          {shown.length === 0 && <p className="text-sm text-muted-foreground">Không có xe nào.</p>}
          {shown.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => pick(s)}
              className="flex cursor-pointer items-center justify-between rounded border-2 bg-card px-3 py-2 text-left shadow-[2px_2px_0_#000] transition-transform hover:translate-x-0.5 hover:translate-y-0.5 hover:bg-accent hover:shadow-none"
            >
              <span>
                <span className="block font-plate">{s.display}</span>
                <span className="text-xs text-muted-foreground">
                  {VEHICLE_LABEL[s.vehicle_type]} · ô {s.slot_id}
                </span>
              </span>
              <span
                className="size-5 shrink-0 rounded border-2"
                style={{ background: s.vehicle_style.color ?? "#9aa0a6" }}
              />
            </button>
          ))}
        </div>
        <Button variant="outline" onClick={() => setPhase({ kind: "idle" })}>
          <XIcon /> Đóng
        </Button>
      </CardContent>
    </Card>
  )
}

const MATCH_STYLE = {
  ok: { status: "success", title: "Biển số khớp với thẻ" },
  suspect: { status: "warning", title: "Nghi model đọc sai, cần bảo vệ xem" },
  mismatch: { status: "error", title: "Biển số KHÔNG khớp với thẻ" },
} as const

/** Exit gate: ticket (or lost ticket), exit photo, plate check, fee, and the guard's decision. */
export function ExitCheckDialog() {
  const phase = useSim((s) => s.phase)
  const lot = useSim((s) => s.lot)
  const release = useSim((s) => s.release)
  const hold = useSim((s) => s.hold)
  const atGate: Session | null = phase.kind === "exit-check" ? phase.session : null

  const [cardId, setCardId] = useState<number | null>(null)
  const [lost, setLost] = useState(false)
  const [lostPlate, setLostPlate] = useState("")
  const [capture, setCapture] = useState<Capture | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [result, setResult] = useState<ExitCheck | null>(null)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)

  // a new vehicle at the gate: its own ticket is preselected
  useEffect(() => {
    setCardId(atGate?.card_id ?? null)
    setLostPlate(atGate?.display ?? "")
    setLost(false)
    setCapture(null)
    setPreview(null)
    setResult(null)
    setReason("")
  }, [atGate?.id, atGate?.card_id, atGate?.display])

  const cardsInUse = useMemo(
    () => (lot?.slots ?? []).flatMap((s) => (s.session ? [s.session] : [])).sort((a, b) => a.card_id - b.card_id),
    [lot],
  )
  if (!atGate) return null

  const shoot = async (file: File) => {
    setPreview(URL.createObjectURL(file))
    setResult(null)
    setBusy(true)
    try {
      setCapture((await parkingApi.capture(file)).capture)
    } catch (e) {
      toast.error("Không nhận diện được", { description: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  const check = async () => {
    if (!capture) return
    setBusy(true)
    try {
      setResult(
        await parkingApi.checkExit(
          lost ? { capture_id: capture.id, plate: lostPlate, lost_card: true } : { capture_id: capture.id, card_id: cardId ?? undefined },
        ),
      )
    } catch (e) {
      toast.error("Không kiểm tra được", { description: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  const letOut = async (override?: string) => {
    if (!result || !capture) return
    setBusy(true)
    try {
      const s = await parkingApi.confirmExit({
        session_id: result.session.id,
        capture_id: capture.id,
        lost_card: result.lost_card,
        override_reason: override,
      })
      toast.success(`Đã thu ${formatVnd(s.fee ?? 0)} · mời xe ra`, {
        description: result.lost_card ? `Thẻ ${s.card_code} đã bị khoá` : `Thẻ ${s.card_code} đã về thùng`,
      })
      release()
    } catch (e) {
      toast.error("Không cho xe ra được", { description: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  const wrongVehicle = result && result.session.id !== atGate.id
  const style = result ? MATCH_STYLE[result.match.status] : null
  // the read is normalized ("54L19999"); show it the way the pipeline formats it ("54-L1 9999")
  const readDisplay = result && (capture?.plates.find((p) => p.text === result.match.read)?.display || result.match.read)

  return (
    <Dialog open onOpenChange={(o) => !o && hold()} disablePointerDismissal>
      <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="font-head text-xl">Cổng ra · Kiểm tra thẻ và biển số</DialogTitle>
          <DialogDescription>
            Biển số lúc ra do camera đọc. Người lái <b>không</b> sửa được, chỉ bảo vệ mới duyệt được trường hợp không khớp.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-3 rounded border-2 bg-card p-3">
              <Label htmlFor="lost">Khách báo mất thẻ</Label>
              <Switch id="lost" checked={lost} onCheckedChange={(v) => { setLost(v); setResult(null) }} />
            </div>
            {lost ? (
              <div className="flex flex-col gap-2">
                <Label htmlFor="lost-plate">Biển số khách khai (bảo vệ tra cứu)</Label>
                <Input id="lost-plate" value={lostPlate} onChange={(e) => { setLostPlate(e.target.value); setResult(null) }} className="font-plate" />
                <p className="text-sm text-muted-foreground">
                  Phí mất thẻ: {formatVnd(lot?.fees[atGate.vehicle_type].lost_card ?? 0)}. Thẻ cũ sẽ bị khoá.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <Label htmlFor="card">Thẻ khách đưa</Label>
                <select
                  id="card"
                  value={cardId ?? ""}
                  onChange={(e) => { setCardId(Number(e.target.value)); setResult(null) }}
                  className="h-10 rounded border-2 bg-card px-3 font-plate shadow-[2px_2px_0_#000]"
                >
                  {cardsInUse.map((s) => (
                    <option key={s.card_id} value={s.card_id}>
                      {s.card_code}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">Đổi sang thẻ khác để thử trường hợp đưa nhầm hoặc dùng thẻ của xe khác.</p>
              </div>
            )}
            {preview ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm font-medium">Ảnh lúc ra</p>
                <PlateImage src={preview} plates={capture?.plates ?? []} />
                <Button size="sm" variant="outline" className="w-fit" onClick={() => { setPreview(null); setCapture(null); setResult(null) }}>
                  Chụp lại
                </Button>
              </div>
            ) : (
              <PhotoInput onFile={shoot} disabled={busy} />
            )}
            <Button onClick={check} disabled={!capture || busy || (lost ? !lostPlate.trim() : !cardId)}>
              {busy ? <Spinner /> : <ScanSearchIcon />} Kiểm tra
            </Button>
          </div>

          <div className="flex flex-col gap-3">
            {!result && (
              <div className="flex h-full min-h-40 items-center justify-center rounded border-2 border-dashed p-4 text-center text-sm text-muted-foreground">
                Chọn thẻ, chụp ảnh biển số rồi bấm Kiểm tra.
              </div>
            )}
            {result && style && (
              <>
                <div className="grid grid-cols-2 gap-2">
                  <figure>
                    <figcaption className="mb-1 text-xs font-bold">LÚC VÀO</figcaption>
                    {result.session.entry_capture ? (
                      <img src={parkingApi.imageUrl(result.session.entry_capture)} alt="Ảnh lúc vào" className="w-full rounded border-2" />
                    ) : (
                      <div className="rounded border-2 p-4 text-xs text-muted-foreground">Không có ảnh</div>
                    )}
                    <p className="mt-1 font-plate">{result.session.display}</p>
                  </figure>
                  <figure>
                    <figcaption className="mb-1 text-xs font-bold">LÚC RA</figcaption>
                    {preview && <img src={preview} alt="Ảnh lúc ra" className="w-full rounded border-2" />}
                    <p className="mt-1 font-plate">{readDisplay || "?"}</p>
                  </figure>
                </div>

                {wrongVehicle ? (
                  <Alert status="error">
                    <HandIcon />
                    <AlertTitle>Thẻ {result.session.card_code} không phải của xe này</AlertTitle>
                    <AlertDescription>
                      Thẻ này gắn với xe {result.session.display} ở ô {result.session.slot_id}. Không cho xe ra.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Alert status={style.status}>
                    <ShieldCheckIcon />
                    <AlertTitle>{style.title}</AlertTitle>
                    <AlertDescription>
                      {result.match.status === "ok"
                        ? `Đúng xe của thẻ ${result.session.card_code}, có thể thu phí và cho ra.`
                        : result.match.reason}
                    </AlertDescription>
                  </Alert>
                )}

                {!wrongVehicle && (
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 rounded border-2 bg-card p-3 text-sm">
                  <dt className="text-muted-foreground">Thẻ</dt>
                  <dd className="font-plate">{result.session.card_code}</dd>
                  <dt className="text-muted-foreground">Thời gian gửi</dt>
                  <dd className="font-medium">{formatDuration(result.duration_s)}</dd>
                  <dt className="text-muted-foreground">Phí</dt>
                  <dd className="font-plate text-lg">
                    {formatVnd(result.fee)}
                    {result.lost_card && <span className="ms-1 font-sans text-xs">(gồm phí mất thẻ)</span>}
                  </dd>
                </dl>
                )}

                {!wrongVehicle && result.match.status !== "ok" && (
                  <div className="flex flex-col gap-2 rounded border-2 bg-yellow-100 p-3">
                    <Label htmlFor="reason">Bảo vệ: lý do cho xe ra</Label>
                    <Textarea
                      id="reason"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="VD: đã đối chiếu giấy đăng ký xe, đúng chủ xe"
                    />
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={hold} disabled={busy}>
            <HandIcon /> Giữ xe lại
          </Button>
          {result && !wrongVehicle && result.match.status === "ok" && (
            <Button onClick={() => letOut()} disabled={busy}>
              <CarFrontIcon /> Thu {formatVnd(result.fee)} · mở barrier
            </Button>
          )}
          {result && !wrongVehicle && result.match.status !== "ok" && (
            <Button onClick={() => letOut(reason)} disabled={busy || !reason.trim()}>
              <ShieldCheckIcon /> Bảo vệ duyệt · thu {formatVnd(result.fee)}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
