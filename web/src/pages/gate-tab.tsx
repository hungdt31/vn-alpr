import { useState } from "react"
import { LogInIcon, LogOutIcon } from "lucide-react"
import { toast } from "sonner"

import { ImageDrop } from "@/components/image-drop"
import { PlateImage } from "@/components/plate-image"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { usePreview } from "@/hooks/use-preview"
import { api, formatDuration, type Direction, type GateResponse } from "@/lib/api"

/** Simulates a gate camera: upload a snapshot, log every valid plate as an entry or exit. */
export function GateTab({ onLogged }: { onLogged: () => void }) {
  const [direction, setDirection] = useState<Direction>("in")
  const [gate, setGate] = useState("main")
  const [preview, setPreview] = usePreview()
  const [result, setResult] = useState<GateResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const run = async (f: File) => {
    setPreview(f)
    setResult(null)
    setLoading(true)
    try {
      const res = await api.gate(direction, f, gate || "main")
      setResult(res)
      if (res.events.length) onLogged()
    } catch (e) {
      toast.error("Ghi lượt thất bại", { description: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }

  const validPlates = result?.plates.filter((p) => p.valid) ?? []
  const skipped = validPlates.filter((p) => !result?.events.some((ev) => ev.plate === p.text))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-2">
          <Label>Hướng</Label>
          <div className="flex gap-2">
            <Button variant={direction === "in" ? "default" : "outline"} onClick={() => setDirection("in")}>
              <LogInIcon /> Vào
            </Button>
            <Button variant={direction === "out" ? "default" : "outline"} onClick={() => setDirection("out")}>
              <LogOutIcon /> Ra
            </Button>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="gate">Cổng</Label>
          <Input id="gate" value={gate} onChange={(e) => setGate(e.target.value)} className="w-40" />
        </div>
      </div>

      {!preview ? (
        <ImageDrop onFile={run} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
          <div className="flex flex-col gap-3">
            <PlateImage src={preview.url} plates={result?.plates ?? []} />
            <Button variant="outline" className="w-fit" onClick={() => setPreview(null)} disabled={loading}>
              Ảnh tiếp theo
            </Button>
          </div>
          <div className="flex flex-col gap-4">
            {loading && (
              <div className="flex items-center gap-3 rounded border-2 bg-card p-4 shadow-md">
                <Spinner className="size-5" />
                <span className="font-medium">Đang xử lý…</span>
              </div>
            )}
            {result?.events.map((ev) => (
              <Alert key={ev.id} status="success">
                {ev.direction === "in" ? <LogInIcon /> : <LogOutIcon />}
                <AlertTitle className="font-plate text-xl">{ev.display}</AlertTitle>
                <AlertDescription>
                  Đã ghi lượt {ev.direction === "in" ? "vào" : "ra"} tại cổng {ev.gate}
                  {ev.duration_s !== undefined && <> · thời gian gửi {formatDuration(ev.duration_s)}</>}
                </AlertDescription>
              </Alert>
            ))}
            {skipped.map((p) => (
              <Alert key={p.text} status="warning">
                <AlertTitle className="font-plate text-xl">{p.display}</AlertTitle>
                <AlertDescription>Bỏ qua: xe này vừa được ghi cùng hướng trong 60 giây.</AlertDescription>
              </Alert>
            ))}
            {result && validPlates.length === 0 && (
              <Alert status="error">
                <AlertTitle>Không có biển hợp lệ</AlertTitle>
                <AlertDescription>
                  {result.plates.length
                    ? `Đọc được ${result.plates.map((p) => p.text || "?").join(", ")} nhưng không khớp định dạng biển VN.`
                    : "Không phát hiện biển số nào trong ảnh."}
                </AlertDescription>
              </Alert>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
