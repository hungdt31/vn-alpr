import { useRef, useState } from "react"
import { ImageUpIcon } from "lucide-react"

import { cn } from "@/lib/utils"

interface ImageDropProps {
  onFile: (file: File) => void
  disabled?: boolean
}

/** Click or drag-and-drop area that hands back a single image file. */
export function ImageDrop({ onFile, disabled }: ImageDropProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const pick = (files: FileList | null) => {
    const file = files?.[0]
    if (file && file.type.startsWith("image/")) onFile(file)
  }

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        pick(e.dataTransfer.files)
      }}
      className={cn(
        "flex w-full cursor-pointer flex-col items-center justify-center gap-3 rounded border-2 border-dashed bg-card px-6 py-10 text-center transition-all",
        "hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60",
        dragging && "translate-x-1 translate-y-1 border-solid bg-primary"
      )}
    >
      <ImageUpIcon className="size-10" strokeWidth={1.75} />
      <span className="font-head text-lg">Thả ảnh vào đây</span>
      <span className="text-sm text-muted-foreground">hoặc bấm để chọn ảnh (JPG, PNG)</span>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          pick(e.target.files)
          e.target.value = "" // allow picking the same file again
        }}
      />
    </button>
  )
}
