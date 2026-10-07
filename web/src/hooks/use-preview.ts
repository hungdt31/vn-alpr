import { useEffect, useState } from "react"

export interface Preview {
  file: File
  url: string
}

/** A picked file plus a blob URL to show it; the URL is revoked when replaced or on unmount. */
export function usePreview() {
  const [preview, setPreview] = useState<Preview | null>(null)

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview.url)
    }
  }, [preview])

  const set = (file: File | null) => setPreview(file ? { file, url: URL.createObjectURL(file) } : null)

  return [preview, set] as const
}
