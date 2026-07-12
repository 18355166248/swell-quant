import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 百分比格式化（带符号），供指标展示。 */
export function pct(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined) return "—";
  return `${x >= 0 ? "+" : ""}${(x * 100).toFixed(digits)}%`;
}

export function num(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined) return "—";
  return x.toFixed(digits);
}
