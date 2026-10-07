import { useState } from "react"
import { ScanSearchIcon } from "lucide-react"
import { toast } from "sonner"

import { ImageDrop } from "@/components/image-drop"
import { PlateCard } from "@/components/plate-card"
import { PlateImage } from "@/components/plate-image"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Spinner } from "@/components/ui/spinner"
import { usePreview } from "@/hooks/use-preview"
import { api, type RecognizeResponse } from "@/lib/api"

export function RecognizeTab() {
  const [preview, setPreview] = usePreview()
  const [result, setResult] = useState<RecognizeResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const run = async (f: File) => {
    setPreview(f)
    setResult(null)
    setLoading(true)
    try {
      setResult(await api.recognize(f))
    } catch (e) {
      toast.error("Nhận diện thất bại", { description: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }

  if (!preview) {
    return <ImageDrop onFile={run} />
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
      <div className="flex flex-col gap-3">
        <PlateImage src={preview.url} plates={result?.plates ?? []} />
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" onClick={() => setPreview(null)} disabled={loading}>
            Chọn ảnh khác
          </Button>
          {result && <Badge variant="secondary">{result.latency_ms} ms</Badge>}
          <span className="truncate text-sm text-muted-foreground">{preview.file.name}</span>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {loading && (
          <div className="flex items-center gap-3 rounded border-2 bg-card p-4 shadow-md">
            <Spinner className="size-5" />
            <span className="font-medium">Đang nhận diện…</span>
          </div>
        )}
        {result && result.plates.length === 0 && (
          <Empty className="rounded border-2 bg-card shadow-md">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <ScanSearchIcon />
              </EmptyMedia>
              <EmptyTitle>Không tìm thấy biển số</EmptyTitle>
              <EmptyDescription>Thử ảnh rõ hơn, hoặc ảnh chụp gần biển số hơn.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        {result?.plates.map((p, i) => <PlateCard key={i} plate={p} index={i} />)}
      </div>
    </div>
  )
}
