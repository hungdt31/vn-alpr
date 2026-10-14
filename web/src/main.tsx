import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import { Toaster } from "@/components/ui/sonner"
import "./index.css"
import App from "./App.tsx"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    {/* the app is light only: with the default "system" theme, a dark OS made sonner paint descriptions #e8e8e8 */}
    <Toaster position="top-right" theme="light" />
  </StrictMode>,
)
