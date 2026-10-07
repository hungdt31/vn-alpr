import { useEffect, useState } from "react"
import { CarFrontIcon, DoorOpenIcon, HistoryIcon, ScanLineIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import { GateTab } from "@/pages/gate-tab"
import { HistoryTab } from "@/pages/history-tab"
import { ParkedTab } from "@/pages/parked-tab"
import { RecognizeTab } from "@/pages/recognize-tab"

function useApiOnline(): boolean | null {
  const [online, setOnline] = useState<boolean | null>(null)
  useEffect(() => {
    const check = () =>
      api
        .health()
        .then(() => setOnline(true))
        .catch(() => setOnline(false))
    check()
    const t = setInterval(check, 10_000)
    return () => clearInterval(t)
  }, [])
  return online
}

export default function App() {
  const online = useApiOnline()
  // bumped after the gate tab logs an event so the history/parked tabs refetch
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <div className="min-h-svh">
      <header className="border-b-2 bg-primary">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-5">
          <div className="flex items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded border-2 bg-card shadow-md">
              <CarFrontIcon className="size-7" />
            </div>
            <div>
              <h1 className="font-plate text-2xl leading-tight sm:text-3xl">VN-ALPR</h1>
              <p className="text-sm font-medium">Nhận diện biển số xe Việt Nam</p>
            </div>
          </div>
          {online === null ? (
            <Badge variant="outline">Đang kết nối API…</Badge>
          ) : online ? (
            <Badge variant="secondary">● API đang chạy</Badge>
          ) : (
            <Badge variant="destructive">● Không kết nối được API</Badge>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        {online === false && (
          <p className="mb-6 rounded border-2 bg-red-100 p-4 text-sm shadow-sm">
            Chưa thấy backend. Chạy <code className="font-mono font-bold">uvicorn app.api.main:app --port 8000</code> ở
            thư mục gốc project, rồi tải lại trang.
          </p>
        )}

        <Tabs defaultValue="recognize" className="gap-6">
          <TabsList className="h-auto w-full flex-wrap sm:w-fit">
            <TabsTrigger value="recognize">
              <ScanLineIcon /> Nhận diện ảnh
            </TabsTrigger>
            <TabsTrigger value="gate">
              <DoorOpenIcon /> Cổng vào/ra
            </TabsTrigger>
            <TabsTrigger value="history">
              <HistoryIcon /> Lịch sử
            </TabsTrigger>
            <TabsTrigger value="parked">
              <CarFrontIcon /> Xe trong bãi
            </TabsTrigger>
          </TabsList>

          <TabsContent value="recognize">
            <RecognizeTab />
          </TabsContent>
          <TabsContent value="gate">
            <GateTab onLogged={() => setRefreshKey((k) => k + 1)} />
          </TabsContent>
          <TabsContent value="history">
            <HistoryTab refreshKey={refreshKey} />
          </TabsContent>
          <TabsContent value="parked">
            <ParkedTab refreshKey={refreshKey} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
