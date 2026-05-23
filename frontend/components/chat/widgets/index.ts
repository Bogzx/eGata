import type { ComponentType } from "react";
import type { WidgetSpec } from "@/lib/types";
import { ChoiceWidget } from "./ChoiceWidget";
import { ConfirmWidget } from "./ConfirmWidget";
import { DateWidget } from "./DateWidget";

type WidgetProps<T extends WidgetSpec["type"]> = {
  spec: Extract<WidgetSpec, { type: T }>;
  onSubmit: (value: string) => void;
};

export const WIDGET_REGISTRY: {
  [K in WidgetSpec["type"]]: ComponentType<WidgetProps<K>>;
} = {
  choice: ChoiceWidget,
  confirm: ConfirmWidget,
  date: DateWidget,
};

export { ChoiceWidget, ConfirmWidget, DateWidget };
