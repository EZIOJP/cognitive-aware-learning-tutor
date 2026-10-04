import { useEffect, useRef, useState, type RefObject } from "react";

/** Create-drag allotment while painting (display step stays separate). */
const CREATE_STEP = 1;
/** Commit to horizontal intent after this much X travel. */
const AXIS_COMMIT_PX = 5;
/**
 * Enter multi-hour mode: pointer must leave the origin row by this fraction
 * of a row (no Alt/Shift — pure motion).
 */
const ROW_BREAKOUT_FRAC = 0.42;

type Props = {
  day: Date;
  /** @deprecated Create always uses 1-minute snap. */
  step?: number;
  containerRef: RefObject<HTMLDivElement | null>;
  onCreate: (args: { start: Date; durationMinutes: number }) => void;
};

type DraftSeg = {
  top: number;
  left: number;
  width: number;
  height: number;
};

type DraftState = {
  snapStart: number;
  snapEnd: number;
  durationMinutes: number;
  segs: DraftSeg[];
};

type FrozenGeo = {
  width: number;
  rowH: number;
  n: number;
};

function snapMin(raw: number, step: number, max: number): number {
  const s = Math.max(1, step);
  const n = Math.round(raw / s) * s;
  return Math.max(0, Math.min(max, n));
}

function softSnap(raw: number, step: number, max: number): number {
  const s = Math.max(1, step);
  const clamped = Math.max(0, Math.min(max, raw));
  const nearest = Math.round(clamped / s) * s;
  const dist = Math.abs(clamped - nearest);
  const pull = s * 0.28;
  if (dist >= pull) return clamped;
  const t = 1 - dist / pull;
  const ease = t * t * (3 - 2 * t);
  return clamped + (nearest - clamped) * ease;
}

function fmtAbs(abs: number): string {
  const h24 = Math.floor(abs / 60) % 24;
  const m = Math.round(abs % 60) % 60;
  const h12 = ((h24 + 11) % 12) + 1;
  const ap = h24 >= 12 ? "PM" : "AM";
  return `${h12}:${String(m).padStart(2, "0")} ${ap}`;
}

function findScrollParents(el: HTMLElement | null): HTMLElement[] {
  const out: HTMLElement[] = [];
  let cur: HTMLElement | null = el;
  while (cur) {
    const st = window.getComputedStyle(cur);
    const oy = st.overflowY;
    if (oy === "auto" || oy === "scroll" || oy === "overlay") out.push(cur);
    cur = cur.parentElement;
  }
  return out;
}

/**
 * Continuum create (option A): one event from anchored start → live end.
 * - Left/right: stay on the start hour (no row hop from tremor / auto-scroll).
 * - Clear vertical travel into another row: blend across hours (partial / full / partial).
 * - No modifier keys.
 */
export function DayGridCreateLayer({ day, containerRef, onCreate }: Props) {
  const step = CREATE_STEP;
  const [draft, setDraft] = useState<DraftState | null>(null);
  const dragRef = useRef<{
    originAbs: number;
    originHour: number;
    originClientX: number;
    originClientY: number;
    /** Live end (absolute minutes); start is always originAbs */
    liveAbs: number;
    /** Once true, Y may change the end hour for the rest of the gesture */
    multiHour: boolean;
    geo: FrozenGeo;
    pointerId: number;
    scrollLocks: { el: HTMLElement; top: number; left: number }[];
    windowScrollX: number;
    windowScrollY: number;
  } | null>(null);
  const onCreateRef = useRef(onCreate);
  onCreateRef.current = onCreate;

  const pendingRef = useRef<DraftState | null>(null);
  const rafRef = useRef(0);
  const draftRef = useRef<DraftState | null>(null);

  useEffect(() => {
    const wrap = containerRef.current;
    if (!wrap) return;

    const setCreating = (on: boolean) => {
      const track = wrap.querySelector(".planner-day-track") as HTMLElement | null;
      if (!track) return;
      if (on) track.setAttribute("data-creating", "1");
      else track.removeAttribute("data-creating");
    };

    let slotEl: HTMLElement | null = null;
    let detachSlot: (() => void) | null = null;

    const daySlot = () =>
      (wrap.querySelector("[data-day-track-body]") as HTMLElement | null) ||
      (wrap.querySelector(".rbc-time-content .rbc-day-slot") as HTMLElement | null);

    const measureGeo = (): FrozenGeo | null => {
      if (!slotEl) return null;
      const col = slotEl.getBoundingClientRect();
      if (col.width < 1 || col.height < 1) return null;
      const n = Math.max(1, slotEl.querySelectorAll("[data-day-track-row]").length || 24);
      return { width: col.width, rowH: col.height / n, n };
    };

    const liveCol = () => slotEl?.getBoundingClientRect() ?? null;

    const minFromX = (clientX: number, geo: FrozenGeo) => {
      const col = liveCol();
      const left = col?.left ?? 0;
      const width = col && col.width > 1 ? col.width : geo.width;
      return Math.max(0, Math.min(60, ((clientX - left) / Math.max(1, width)) * 60));
    };

    const hourFromY = (clientY: number, geo: FrozenGeo) => {
      const col = liveCol();
      const top = col?.top ?? 0;
      return Math.max(0, Math.min(geo.n - 1, Math.floor((clientY - top) / Math.max(1, geo.rowH))));
    };

    /** Continuum segments: partial first/last hour, full hours in between. */
    const buildContinuumSegs = (startAbs: number, endAbs: number, geo: FrozenGeo): DraftSeg[] => {
      let a = Math.min(startAbs, endAbs);
      let b = Math.max(startAbs, endAbs);
      if (b - a < 0.35) b = a + Math.max(0.35, step * 0.35);
      a = Math.max(0, a);
      b = Math.min(geo.n * 60, b);

      const col = liveCol();
      const width = col && col.width > 1 ? col.width : geo.width;
      const out: DraftSeg[] = [];
      let cursor = a;
      while (cursor < b - 1e-6) {
        const hour = Math.floor(cursor / 60);
        if (hour >= geo.n) break;
        const hourStart = hour * 60;
        const hourEnd = hourStart + 60;
        const segStart = cursor;
        const segEnd = Math.min(b, hourEnd);
        const startMin = segStart - hourStart;
        const endMin = segEnd - hourStart;
        out.push({
          top: hour * geo.rowH,
          height: geo.rowH,
          left: (startMin / 60) * width,
          width: Math.max(3, ((endMin - startMin) / 60) * width),
        });
        cursor = segEnd;
        if (segEnd <= segStart) break;
      }
      return out;
    };

    const hardRange = (originAbs: number, liveAbs: number) => {
      let a = Math.min(originAbs, liveAbs);
      let b = Math.max(originAbs, liveAbs);
      a = snapMin(a, step, 24 * 60 - step);
      b = snapMin(b, step, 24 * 60);
      if (b <= a) b = a + step;
      return { snapStart: a, snapEnd: b, durationMinutes: b - a };
    };

    const restoreScroll = () => {
      const d = dragRef.current;
      if (!d) return;
      for (const s of d.scrollLocks) {
        if (s.el.scrollTop !== s.top) s.el.scrollTop = s.top;
        if (s.el.scrollLeft !== s.left) s.el.scrollLeft = s.left;
      }
      if (window.scrollX !== d.windowScrollX || window.scrollY !== d.windowScrollY) {
        window.scrollTo(d.windowScrollX, d.windowScrollY);
      }
    };

    const paintFromDrag = () => {
      const d = dragRef.current;
      if (!d) return;
      restoreScroll();
      const hard = hardRange(d.originAbs, d.liveAbs);
      const next: DraftState = {
        snapStart: hard.snapStart,
        snapEnd: hard.snapEnd,
        durationMinutes: hard.durationMinutes,
        segs: buildContinuumSegs(d.originAbs, d.liveAbs, d.geo),
      };
      pendingRef.current = next;
      if (rafRef.current) return;
      rafRef.current = window.requestAnimationFrame(() => {
        rafRef.current = 0;
        restoreScroll();
        const p = pendingRef.current;
        if (!p) return;
        const prev = draftRef.current;
        if (
          prev &&
          prev.snapStart === p.snapStart &&
          prev.snapEnd === p.snapEnd &&
          prev.segs.length === p.segs.length
        ) {
          let same = true;
          for (let i = 0; i < p.segs.length; i++) {
            const a = prev.segs[i];
            const b = p.segs[i];
            if (
              Math.abs(a.left - b.left) > 0.4 ||
              Math.abs(a.width - b.width) > 0.4 ||
              Math.abs(a.top - b.top) > 0.4
            ) {
              same = false;
              break;
            }
          }
          if (same) return;
        }
        draftRef.current = p;
        setDraft(p);
      });
    };

    const sampleLive = (e: PointerEvent, d: NonNullable<typeof dragRef.current>) => {
      const min = softSnap(minFromX(e.clientX, d.geo), step, 60);
      const hourRaw = hourFromY(e.clientY, d.geo);
      const absDx = Math.abs(e.clientX - d.originClientX);
      const absDy = Math.abs(e.clientY - d.originClientY);
      const breakoutPx = d.geo.rowH * ROW_BREAKOUT_FRAC;

      // Engage multi-hour when the pointer has clearly entered another row
      // (distance past origin row), not from tiny diagonal tremor.
      if (
        !d.multiHour &&
        hourRaw !== d.originHour &&
        absDy >= breakoutPx &&
        absDy > absDx * 0.85
      ) {
        d.multiHour = true;
      }
      // Also engage if they've traveled ~half a row vertically even before
      // hour index flips (smooth blend toward the boundary).
      if (!d.multiHour && absDy >= breakoutPx && absDy > absDx + AXIS_COMMIT_PX) {
        d.multiHour = true;
      }

      if (d.multiHour) {
        d.liveAbs = hourRaw * 60 + min;
      } else {
        // Sticky single-hour: end stays on the origin row
        d.liveAbs = d.originHour * 60 + min;
      }

      // Minimum visible span
      if (Math.abs(d.liveAbs - d.originAbs) < 0.35) {
        d.liveAbs = d.originAbs + (d.liveAbs >= d.originAbs ? step * 0.35 : -step * 0.35);
      }
    };

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      const t = e.target as HTMLElement;
      if (t.closest(".hour-seg-block, .rbc-event, button, a, input, textarea, [role='dialog']")) {
        return;
      }
      if (!slotEl) return;
      const geo = measureGeo();
      if (!geo) return;

      const hour = hourFromY(e.clientY, geo);
      const min = snapMin(softSnap(minFromX(e.clientX, geo), step, 60), step, 60 - step);
      const originAbs = hour * 60 + min;

      dragRef.current = {
        originAbs,
        originHour: hour,
        originClientX: e.clientX,
        originClientY: e.clientY,
        liveAbs: originAbs + step,
        multiHour: false,
        geo,
        pointerId: e.pointerId,
        scrollLocks: findScrollParents(slotEl).map((el) => ({
          el,
          top: el.scrollTop,
          left: el.scrollLeft,
        })),
        windowScrollX: window.scrollX,
        windowScrollY: window.scrollY,
      };
      setCreating(true);
      paintFromDrag();
      try {
        slotEl.setPointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
      e.preventDefault();
      e.stopPropagation();
    };

    const onPointerMove = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d || e.pointerId !== d.pointerId) return;
      restoreScroll();
      sampleLive(e, d);
      paintFromDrag();
      e.preventDefault();
      e.stopPropagation();
    };

    const clearDrag = () => {
      dragRef.current = null;
      pendingRef.current = null;
      if (rafRef.current) {
        window.cancelAnimationFrame(rafRef.current);
        rafRef.current = 0;
      }
      draftRef.current = null;
      setDraft(null);
      setCreating(false);
    };

    const finish = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d || e.pointerId !== d.pointerId) return;
      restoreScroll();
      sampleLive(e, d);
      const hard = hardRange(d.originAbs, d.liveAbs);
      const start = new Date(day);
      start.setHours(0, 0, 0, 0);
      start.setMinutes(hard.snapStart);

      clearDrag();
      onCreateRef.current({
        start,
        durationMinutes: Math.max(step, hard.durationMinutes),
      });
      e.preventDefault();
      e.stopPropagation();
    };

    const onPointerUp = (e: PointerEvent) => finish(e);
    const onPointerCancel = (e: PointerEvent) => {
      if (dragRef.current?.pointerId === e.pointerId) clearDrag();
    };
    const onScroll = () => {
      if (dragRef.current) restoreScroll();
    };

    const attach = (el: HTMLElement) => {
      if (slotEl === el) return;
      detachSlot?.();
      slotEl = el;
      el.addEventListener("pointerdown", onPointerDown, true);
      detachSlot = () => {
        el.removeEventListener("pointerdown", onPointerDown, true);
      };
    };

    const tryAttach = () => {
      const el = daySlot();
      if (el) attach(el);
    };

    tryAttach();
    const ro = new ResizeObserver(tryAttach);
    ro.observe(wrap);
    const mo = new MutationObserver(tryAttach);
    mo.observe(wrap, { childList: true, subtree: true });
    window.addEventListener("pointermove", onPointerMove, true);
    window.addEventListener("pointerup", onPointerUp, true);
    window.addEventListener("pointercancel", onPointerCancel, true);
    window.addEventListener("scroll", onScroll, true);
    const t = window.setTimeout(tryAttach, 50);
    const t2 = window.setTimeout(tryAttach, 200);

    return () => {
      detachSlot?.();
      ro.disconnect();
      mo.disconnect();
      window.removeEventListener("pointermove", onPointerMove, true);
      window.removeEventListener("pointerup", onPointerUp, true);
      window.removeEventListener("pointercancel", onPointerCancel, true);
      window.removeEventListener("scroll", onScroll, true);
      window.clearTimeout(t);
      window.clearTimeout(t2);
      if (rafRef.current) window.cancelAnimationFrame(rafRef.current);
      setCreating(false);
    };
  }, [containerRef, day]);

  if (!draft || draft.segs.length === 0) return null;

  const label = `${fmtAbs(draft.snapStart)} – ${fmtAbs(draft.snapEnd)} · ${draft.durationMinutes}m`;

  return (
    <div className="day-grid-create-preview" aria-hidden data-active="1">
      <div className="day-grid-create-preview__guides" />
      {draft.segs.map((s, i) => (
        <div
          key={i}
          className="day-grid-create-preview__seg"
          style={{
            position: "absolute",
            top: s.top,
            left: s.left,
            width: s.width,
            height: s.height,
            zIndex: 6,
            pointerEvents: "none",
          }}
        >
          <div className="day-grid-create-preview__block">
            {i === 0 ? <span className="day-grid-create-preview__label">{label}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
