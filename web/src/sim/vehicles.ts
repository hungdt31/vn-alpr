import type { VehicleStyle, VehicleType } from "@/lib/parking-api"

export interface VehicleModel {
  id: string
  type: VehicleType
  label: string
}

/** Low-poly vehicles drawn from boxes and cylinders in scene/vehicle.tsx. */
export const VEHICLE_MODELS: VehicleModel[] = [
  { id: "sedan", type: "car", label: "Sedan" },
  { id: "suv", type: "car", label: "SUV" },
  { id: "hatchback", type: "car", label: "Hatchback" },
  { id: "pickup", type: "car", label: "Bán tải" },
  { id: "scooter", type: "motorbike", label: "Xe tay ga" },
  { id: "underbone", type: "motorbike", label: "Xe số" },
  { id: "sport", type: "motorbike", label: "Xe côn tay" },
]

export const VEHICLE_COLORS = [
  { value: "#e63946", label: "Đỏ" },
  { value: "#ffdc58", label: "Vàng" },
  { value: "#2a9d8f", label: "Xanh ngọc" },
  { value: "#457b9d", label: "Xanh dương" },
  { value: "#f4a261", label: "Cam" },
  { value: "#8338ec", label: "Tím" },
  { value: "#f5f0e6", label: "Trắng" },
  { value: "#9aa0a6", label: "Bạc" },
  { value: "#262320", label: "Đen" },
]

export interface VehicleSpec extends VehicleStyle {
  type: VehicleType
}

export function modelsOf(type: VehicleType): VehicleModel[] {
  return VEHICLE_MODELS.filter((m) => m.type === type)
}

export function randomSpec(): VehicleSpec {
  const model = VEHICLE_MODELS[Math.floor(Math.random() * VEHICLE_MODELS.length)]
  const color = VEHICLE_COLORS[Math.floor(Math.random() * VEHICLE_COLORS.length)].value
  return { type: model.type, model: model.id, color }
}

/** Style stored with a session may be partial (e.g. sessions created through the API without a look). */
export function specOf(type: VehicleType, style: Partial<VehicleStyle>): VehicleSpec {
  return { type, model: style.model ?? modelsOf(type)[0].id, color: style.color ?? "#9aa0a6" }
}
