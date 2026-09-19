import { useSession } from "./store";
import type { components } from "./generated-api";
export type Patient = components["schemas"]["PatientOut"];
export type Exercise = components["schemas"]["ExerciseOut"];
export type Assignment = components["schemas"]["AssignmentOut"];
export type Session = components["schemas"]["SessionOut"];
export type Joint = {
  x: number;
  y: number;
  z?: number;
  visibility: number;
  inferred?: boolean;
};
export type Frame = {
  seq: number;
  captured_at: string;
  coordinate_system: string;
  units: string;
  image_width: number;
  image_height: number;
  joints: Record<string, Joint>;
  tracking_valid: boolean;
};
export async function api<T>(
  path: string,
  body?: unknown,
  token?: string,
): Promise<T> {
  const auth = token ?? useSession.getState().token;
  const response = await fetch(`/api/v1${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(auth ? { Authorization: `Bearer ${auth}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    const err = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail),
    );
  }
  return response.json();
}
export const errorText = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
