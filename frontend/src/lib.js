// Shared helpers for the RADAR UI.

export const BAND_COLOR = {
  good: "var(--good)",
  warning: "var(--warning)",
  serious: "var(--serious)",
  critical: "var(--critical)",
};

export function bandColor(band) {
  return BAND_COLOR[band] || "var(--ink-3)";
}

export function gradeColor(grade) {
  return (
    { A: "var(--good)", B: "var(--warning)", C: "var(--serious)", D: "var(--critical)" }[
      grade
    ] || "var(--ink-3)"
  );
}

export function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (_) {
    return iso;
  }
}
