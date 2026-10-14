import { useEffect, useMemo } from "react"
import * as THREE from "three"

interface TextTextureOptions {
  lines: string[]
  width: number
  height: number
  background?: string
  color?: string
  border?: string
  font?: string
}

/** Text drawn on a canvas, used for license plates and slot labels (no font download needed). */
export function useTextTexture({
  lines,
  width,
  height,
  background = "#ffffff",
  color = "#000000",
  border,
  font = '"Archivo Black", "Arial Black", Arial, sans-serif',
}: TextTextureOptions): THREE.CanvasTexture {
  const key = lines.join("\n")
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas")
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext("2d")!
    ctx.fillStyle = background
    ctx.fillRect(0, 0, width, height)
    if (border) {
      const b = Math.round(height * 0.06)
      ctx.strokeStyle = border
      ctx.lineWidth = b
      ctx.strokeRect(b / 2, b / 2, width - b, height - b)
    }
    ctx.fillStyle = color
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"
    const lineH = height / lines.length
    lines.forEach((line, i) => {
      let size = lineH * 0.72
      ctx.font = `${size}px ${font}`
      const maxW = width * 0.88
      const w = ctx.measureText(line).width
      if (w > maxW) {
        size *= maxW / w
        ctx.font = `${size}px ${font}`
      }
      ctx.fillText(line, width / 2, lineH * (i + 0.5) + size * 0.04)
    })
    const tex = new THREE.CanvasTexture(canvas)
    tex.colorSpace = THREE.SRGBColorSpace
    tex.anisotropy = 4
    return tex
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` covers `lines`
  }, [key, width, height, background, color, border, font])

  useEffect(() => () => texture.dispose(), [texture])
  return texture
}

/** "54-L1 9999" -> ["54-L1", "9999"] for a 2-line plate; 1-line plates stay as one line. */
export function plateLines(display: string, twoLine: boolean): string[] {
  if (!display) return twoLine ? ["--", "----"] : ["-- ----"]
  if (!twoLine) return [display.replace(" ", "-")]
  const [head, ...rest] = display.split(/[\s/]+/)
  if (rest.length) return [head, rest.join(" ")]
  const m = display.match(/^(.*?)-(.*)$/) // "54L1-9999" typed on one line
  return m ? [m[1], m[2]] : [display]
}
