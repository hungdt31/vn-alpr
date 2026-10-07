import { useState } from "react"

import type { PlateResult } from "@/lib/api"

interface PlateImageProps {
  src: string
  plates: PlateResult[]
}

/** The uploaded image with each detected plate drawn on top (SVG in image pixel coordinates). */
export function PlateImage({ src, plates }: PlateImageProps) {
  const [loaded, setLoaded] = useState<{ src: string; w: number; h: number } | null>(null)
  const size = loaded?.src === src ? loaded : null // ignore the size of a previous image

  return (
    <div className="relative overflow-hidden rounded border-2 bg-card shadow-md">
      <img
        src={src}
        alt="Ảnh đã tải lên"
        className="block h-auto w-full"
        onLoad={(e) => setLoaded({ src, w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
      />
      {size && (
        <svg
          className="pointer-events-none absolute inset-0 size-full"
          viewBox={`0 0 ${size.w} ${size.h}`}
          preserveAspectRatio="none"
        >
          {plates.map((p, i) => {
            const [x1, y1, x2, y2] = p.box
            const stroke = Math.max(3, size.w / 250)
            const fontSize = Math.max(16, size.w / 35)
            const label = p.valid ? p.display : `${p.text || "?"} (?)`
            const color = p.valid ? "#ffdc58" : "#e63946"
            return (
              <g key={i}>
                <rect
                  x={x1}
                  y={y1}
                  width={x2 - x1}
                  height={y2 - y1}
                  fill="none"
                  stroke="#000"
                  strokeWidth={stroke * 2}
                />
                <rect x={x1} y={y1} width={x2 - x1} height={y2 - y1} fill="none" stroke={color} strokeWidth={stroke} />
                <rect
                  x={x1}
                  y={Math.max(0, y1 - fontSize * 1.5)}
                  width={label.length * fontSize * 0.68 + fontSize}
                  height={fontSize * 1.5}
                  fill={color}
                  stroke="#000"
                  strokeWidth={stroke}
                />
                <text
                  x={x1 + fontSize * 0.5}
                  y={Math.max(0, y1 - fontSize * 1.5) + fontSize * 1.1}
                  fontSize={fontSize}
                  fontFamily="'Archivo Black', sans-serif"
                  fill="#000"
                >
                  {label}
                </text>
              </g>
            )
          })}
        </svg>
      )}
    </div>
  )
}
