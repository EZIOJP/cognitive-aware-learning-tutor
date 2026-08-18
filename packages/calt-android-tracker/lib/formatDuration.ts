/** Hours + minutes labels (storage stays in minutes). */
export function formatHoursMins(totalMinutes: number | null | undefined): string {
  if (totalMinutes == null || Number.isNaN(Number(totalMinutes))) return "—";
  const n = Math.max(0, Math.round(Number(totalMinutes)));
  const h = Math.floor(n / 60);
  const m = n % 60;
  const hours = h === 1 ? "1 hour" : `${h} hours`;
  const mins = m === 1 ? "1 min" : `${m} mins`;
  if (h === 0) return `${hours} ${mins}`;
  if (m === 0) return hours;
  return `${hours} ${mins}`;
}

export function formatHoursMinsPair(
  done: number | null | undefined,
  goal: number | null | undefined,
): string {
  return `${formatHoursMins(done)} / ${formatHoursMins(goal)}`;
}
