import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { PlateResult } from "@/lib/api"

/** Big plate text plus the numbers behind it (confidence, line split, raw OCR). */
export function PlateCard({ plate, index }: { plate: PlateResult; index: number }) {
  return (
    <Card className={plate.valid ? "" : "bg-red-100"}>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-muted-foreground">Biển #{index + 1}</span>
          {plate.valid ? <Badge>Hợp lệ</Badge> : <Badge variant="destructive">Không khớp mẫu</Badge>}
        </div>
        <CardTitle className="font-plate text-3xl tracking-wide">{plate.valid ? plate.display : plate.text || "?"}</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted-foreground">Loại biển</dt>
          <dd className="font-medium">{plate.two_line ? "2 dòng" : "1 dòng"}</dd>
          <dt className="text-muted-foreground">Phát hiện</dt>
          <dd className="font-medium">{(plate.det_conf * 100).toFixed(1)}%</dd>
          <dt className="text-muted-foreground">Đọc chữ (OCR)</dt>
          <dd className="font-medium">{(plate.ocr_conf * 100).toFixed(1)}%</dd>
          <dt className="text-muted-foreground">OCR thô</dt>
          <dd className="font-mono font-medium">{plate.raw_lines.join(" / ") || "—"}</dd>
        </dl>
      </CardContent>
    </Card>
  )
}
