import { useEffect, useRef, useState } from "react"
import { CameraIcon, ImageUpIcon } from "lucide-react"

import { ImageDrop } from "@/components/image-drop"
import { Button } from "@/components/ui/button"

/** Camera snapshot for a gate: upload a photo (default) or take one with the webcam. */
export function PhotoInput({ onFile, disabled }: { onFile: (file: File) => void; disabled?: boolean }) {
  const [mode, setMode] = useState<"upload" | "webcam">("upload")
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <Button size="sm" variant={mode === "upload" ? "default" : "outline"} onClick={() => setMode("upload")}>
          <ImageUpIcon /> Tải ảnh lên
        </Button>
        <Button size="sm" variant={mode === "webcam" ? "default" : "outline"} onClick={() => setMode("webcam")}>
          <CameraIcon /> Webcam
        </Button>
      </div>
      {mode === "upload" ? <ImageDrop onFile={onFile} disabled={disabled} /> : <Webcam onFile={onFile} disabled={disabled} />}
    </div>
  )
}

function Webcam({ onFile, disabled }: { onFile: (file: File) => void; disabled?: boolean }) {
  const video = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let stream: MediaStream | null = null
    let cancelled = false
    navigator.mediaDevices
      ?.getUserMedia({ video: { width: { ideal: 1280 } } })
      .then((s) => {
        if (cancelled) return s.getTracks().forEach((t) => t.stop())
        stream = s
        if (video.current) video.current.srcObject = s
      })
      .catch((e: Error) => setError(e.message))
    if (!navigator.mediaDevices) setError("Trình duyệt không hỗ trợ webcam (cần http://localhost hoặc https)")
    return () => {
      cancelled = true
      stream?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const snap = () => {
    const v = video.current
    if (!v || !v.videoWidth) return
    const canvas = document.createElement("canvas")
    canvas.width = v.videoWidth
    canvas.height = v.videoHeight
    canvas.getContext("2d")!.drawImage(v, 0, 0)
    canvas.toBlob((blob) => blob && onFile(new File([blob], "webcam.jpg", { type: "image/jpeg" })), "image/jpeg", 0.92)
  }

  if (error) {
    return <p className="rounded border-2 bg-red-100 p-3 text-sm">Không mở được webcam: {error}</p>
  }
  return (
    <div className="flex flex-col gap-2">
      <video ref={video} autoPlay playsInline muted className="w-full rounded border-2 bg-black" />
      <Button onClick={snap} disabled={disabled}>
        <CameraIcon /> Chụp
      </Button>
    </div>
  )
}
