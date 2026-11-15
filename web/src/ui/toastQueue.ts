// Event toasts, throttled: at most two on screen, each up for a minimum time before a newer one may replace it, and a
// short queue that drops the least important when events arrive faster than they can be read (16x). Pure code, no
// React, no stores (tested by hud.test.mjs); state/app.ts holds the state and calls these.

/** At most this many toasts show at once. */
export const MAX_VISIBLE = 2;
/** A toast stays up at least this long before a queued one may take its place. */
export const MIN_SHOW_MS = 1600;
/** At most this many wait; beyond that the least important (then the oldest) is dropped. */
export const QUEUE_MAX = 2;

export interface Queued {
  id: number;
  kind: string;
}

export interface ToastQueueState<T extends Queued> {
  /** On screen, oldest first, with the time each went up. */
  visible: { toast: T; at: number }[];
  /** Waiting, in arrival order. */
  queue: T[];
}

export const emptyToasts = <T extends Queued>(): ToastQueueState<T> => ({ visible: [], queue: [] });

/** Higher shows first and is dropped last: losing the ship, then the alarm and landfall, then trades, then notes. */
export function priorityOf(kind: string): number {
  switch (kind) {
    case "margin_call":
    case "sunk":
      return 3;
    case "alarm":
    case "all_clear":
    case "land":
      return 2;
    case "market":
      return 0;
    default:
      return 1;
  }
}

/** Queue a toast and show what may show now. */
export function pushToastQ<T extends Queued>(s: ToastQueueState<T>, toast: T, now: number): ToastQueueState<T> {
  let queue = [...s.queue, toast];
  while (queue.length > QUEUE_MAX) {
    // Drop the least important; among equals the oldest.
    let k = 0;
    for (let j = 1; j < queue.length; j++) if (priorityOf(queue[j].kind) < priorityOf(queue[k].kind)) k = j;
    queue = queue.filter((_, j) => j !== k);
  }
  return tickToastQ({ visible: s.visible, queue }, now);
}

/**
 * Promote waiting toasts: into a free slot at once; otherwise in place of the oldest on screen once it has been up
 * MIN_SHOW_MS. The most important waiting toast goes first (the oldest among equals).
 */
export function tickToastQ<T extends Queued>(s: ToastQueueState<T>, now: number): ToastQueueState<T> {
  let visible = s.visible;
  let queue = s.queue;
  while (queue.length > 0) {
    if (visible.length >= MAX_VISIBLE) {
      if (now - visible[0].at < MIN_SHOW_MS) break;
      visible = visible.slice(1);
    }
    let k = 0;
    for (let j = 1; j < queue.length; j++) if (priorityOf(queue[j].kind) > priorityOf(queue[k].kind)) k = j;
    visible = [...visible, { toast: queue[k], at: now }];
    queue = queue.filter((_, j) => j !== k);
  }
  return visible === s.visible && queue === s.queue ? s : { visible, queue };
}

/** A toast's lifetime ended (or it was dismissed): free its slot. */
export function dropToastQ<T extends Queued>(s: ToastQueueState<T>, id: number, now: number): ToastQueueState<T> {
  return tickToastQ({ visible: s.visible.filter((v) => v.toast.id !== id), queue: s.queue.filter((t) => t.id !== id) }, now);
}
