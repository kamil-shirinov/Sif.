import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  HistogramSeries,
  type CandlestickData,
  type HistogramData,
  LineStyle,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
  type WhitespaceData,
} from "lightweight-charts";
import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { useFrameIndex, useTimeline } from "../state/timeline";
import { useApp, type LiveCandles } from "../state/app";
import { useSurvive } from "../state/survive";
import { fmtUtc } from "../lib/format";

/** The four price arrays the chart draws: the bundle's own, or the server's candles laid onto its frames. */
interface PriceSeries {
  open: number[];
  high: number[];
  low: number[];
  mid: number[];
}

/** Minutes per candle when the bundle's own one-minute bars are drawn. */
export const BUCKET = 5;
/** Frames per candle for server bars of `k` frames: at least BUCKET, and a whole number of server bars. */
export const chartBucketFrames = (k: number) => k * Math.ceil(BUCKET / k);

interface BucketAgg {
  time: UTCTimestamp;
  first: number; // first frame
  open: number;
  high: number;
  low: number;
  close: number;
  maxRisk: number;
  meanSpread: number;
  /** Every frame of the candle is in a closed market. */
  closed: boolean;
}

/**
 * One candle from frames first..upto (inclusive). Server bars coarser than a frame count only once the playhead has
 * passed them whole; while one is still in progress, and for any frame the server did not cover, the bundle's own
 * minute bars draw the candle, so the chart never shows prices from after the playhead.
 */
function aggregate(b: Bundle, px: PriceSeries, live: LiveCandles | null, closedAt: Uint8Array | null, first: number, upto: number): BucketAgg {
  const s = b.series;
  let open = NaN;
  let close = NaN;
  let high = -Infinity;
  let low = Infinity;
  const take = (o: number, h: number, l: number, c: number) => {
    if (Number.isNaN(open)) open = o;
    high = Math.max(high, h);
    low = Math.min(low, l);
    close = c;
  };
  let i = first;
  while (i <= upto) {
    const ri = live && live.rowAt.length > 0 ? live.rowAt[i] : -1;
    const row = ri >= 0 && live ? live.rows[ri] : null;
    if (row && row.first === i && i + row.span - 1 <= upto) {
      take(row.open, row.high, row.low, row.close);
      i += row.span;
    } else {
      take(px.open[i], px.high[i], px.low[i], px.mid[i]);
      i += 1;
    }
  }
  let maxRisk = 0;
  let spread = 0;
  let closed = closedAt !== null;
  for (let j = first; j <= upto; j++) {
    maxRisk = Math.max(maxRisk, s.risk[j]);
    spread += s.spread_bp[j];
    if (closedAt && closedAt[j] !== 1) closed = false;
  }
  return {
    time: (b.t0 + first * b.step_s) as UTCTimestamp,
    first,
    open,
    high,
    low,
    close,
    maxRisk,
    meanSpread: spread / (upto - first + 1),
    closed,
  };
}

const CLOSED_COLOR = "rgba(120, 132, 150, 0.4)";

function riskColor(r: number): string {
  if (r >= 0.7) return "rgba(239, 83, 80, 0.9)";
  if (r >= 0.45) return "rgba(245, 166, 35, 0.85)";
  if (r >= 0.3) return "rgba(214, 196, 80, 0.7)";
  return "rgba(80, 160, 130, 0.55)";
}

const bucketTime = (b: Bundle, i: number, size: number) => (b.t0 + Math.floor(i / size) * size * b.step_s) as UTCTimestamp;

/** A marker's word, placed by us in chart-host pixels (centre x, top y). */
interface MarkerLabel {
  key: string;
  text: string;
  color: string;
  x: number;
  y: number;
}
const LABEL_LINE = 12; // px between stacked labels
function sameLabels(a: MarkerLabel[], b: MarkerLabel[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i].key !== b[i].key || Math.abs(a[i].x - b[i].x) > 0.5 || Math.abs(a[i].y - b[i].y) > 0.5) return false;
  }
  return true;
}

export function MarketChart({ bundle, derived, large = false }: { bundle: Bundle; derived: Derived; large?: boolean }) {
  const el = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const riskStrip = useRef<ISeriesApi<"Histogram"> | null>(null);
  const markers = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const marginLine = useRef<IPriceLine | null>(null);
  const priceRange = useRef<{ lo: number; hi: number }>({ lo: 0, hi: 0 });
  const frame = useFrameIndex();
  const [hover, setHover] = useState<BucketAgg | null>(null);
  const [labels, setLabels] = useState<MarkerLabel[]>([]);
  const [layoutTick, setLayoutTick] = useState(0); // bumped when the chart is resized, so the labels are placed again
  const n = derived.n;
  const decimals = derived.priceDecimals;
  const closedAt = derived.closed;
  const player = derived.player;
  // With a live server (health.tiger) the candles come from GET /api/candles, at whatever bar size it used; otherwise from the bundle.
  const live = useApp((st) => (st.live && st.live.seq === st.bundleSeq ? st.live : null));
  const px: PriceSeries = live ?? bundle.series;
  const B = live ? chartBucketFrames(live.bucketFrames) : BUCKET; // frames per candle
  const nBuckets = Math.ceil(n / B);
  const showSpread = bundle.source !== "yahoo"; // Yahoo has trades but no quotes: its spread_bp is 0, not a measured spread
  // Survive mode: the chart is the player's trading screen. Seeking is off, and the margin-call line is drawn.
  const survive = useApp((st) => st.mode === "survive");
  const setupLine = useSurvive((st) => (st.phase === "setup" ? st.line : null));
  const sim = useSurvive((st) => st.sim);
  const marginPrice = survive ? (setupLine ? setupLine.price : sim ? sim.liq[Math.min(n - 1, frame)] : NaN) : NaN;

  // All markers, revealed as the playhead passes them.
  const allMarkers = useMemo(() => {
    const out: { i: number; text: string; m: SeriesMarker<Time> }[] = [];
    out.push({
      i: bundle.storm.onset_i,
      text: "Onset",
      m: { time: bucketTime(bundle, bundle.storm.onset_i, B), position: "aboveBar", shape: "circle", color: "#e0e6ee" },
    });
    const releases = new Set<number>();
    // The chart draws only the shapes. The words are our own DOM labels (see `labels` below): the library centres
    // every label on its marker, so two events in the same or neighbouring candles printed on top of each other.
    const mark = (i: number, position: "aboveBar" | "belowBar", shape: SeriesMarker<Time>["shape"], color: string, text: string) =>
      out.push({ i, text, m: { time: bucketTime(bundle, i, B), position, shape, color } });
    for (const e of bundle.events) {
      // In Survive the demo ships' trades are not the player's: the player's own are marked below.
      if (player && (e.type === "cut" || e.type === "restore" || e.type === "margin_call")) continue;
      if (e.type === "alarm") mark(e.i, "aboveBar", "arrowDown", "#f5a623", "Alarm");
      if (e.type === "margin_call") mark(e.i, "belowBar", "square", "#ef5350", "Margin call");
      if (e.type === "squall") mark(e.i, "aboveBar", "circle", "#f0b44c", "Squall");
      if (e.type === "fair_wind") mark(e.i, "aboveBar", "arrowUp", "#5ecf9a", "Fair wind");
      if (e.type === "watch" && e.at_i !== undefined) releases.add(e.at_i);
    }
    // Cuts and restores at their fill frames (cut_i: one bar after the alarm), from the ships' derived actions:
    // the cut / restore events when the bundle has them, else ships.*.cut_i / restore_i. Same frames as the splash and toast.
    if (!player) {
      for (const k of ["prepared", "unprepared"] as const) {
        for (const a of derived.ships[k].actions) mark(a.i, "belowBar", a.kind === "cut" ? "arrowDown" : "arrowUp", "#7cc4ff", a.kind === "cut" ? "Cut" : "Restore");
      }
    }
    if (bundle.storm.kind === "scheduled" && bundle.storm.event_i !== undefined) releases.add(bundle.storm.event_i);
    for (const i of releases) mark(i, "aboveBar", "circle", "#d6c450", "Release");
    if (player) {
      for (const a of player.actions) mark(a.i, "belowBar", a.kind === "cut" ? "arrowDown" : "arrowUp", "#ffd27a", a.kind === "cut" ? "You cut" : "You restore");
      if (player.marginCallI !== null) mark(player.marginCallI, "belowBar", "square", "#ef5350", "Sunk");
    }
    out.sort((a, b) => a.i - b.i);
    return out;
  }, [bundle, derived, player, B]);

  useEffect(() => {
    const host = el.current;
    if (!host) return;
    const chart = createChart(host, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a9b6c4",
        fontSize: 11,
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        attributionLogo: true,
      },
      grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.05)" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.12)", scaleMargins: { top: 0.16, bottom: 0.24 } },
      timeScale: { borderColor: "rgba(255,255,255,0.12)", timeVisible: true, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
      handleScroll: false,
      handleScale: false,
      localization: { priceFormatter: (p: number) => p.toFixed(decimals) },
    });
    const c = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
      priceFormat: { type: "price", precision: decimals, minMove: Math.pow(10, -decimals) },
    });
    const r = chart.addSeries(HistogramSeries, { priceScaleId: "risk", priceLineVisible: false, lastValueVisible: false, base: 0 });
    chart.priceScale("risk").applyOptions({ scaleMargins: { top: 0.86, bottom: 0 }, visible: false });
    // Fix the price range to the whole storm so candles do not rescale as they are revealed.
    let lo = Infinity;
    let hi = -Infinity;
    for (let i = 0; i < n; i++) {
      lo = Math.min(lo, px.low[i]);
      hi = Math.max(hi, px.high[i]);
    }
    for (const row of live?.rows ?? []) {
      lo = Math.min(lo, row.low);
      hi = Math.max(hi, row.high);
    }
    const pad = (hi - lo) * 0.04;
    priceRange.current = { lo: lo - pad, hi: hi + pad };
    c.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: lo - pad, maxValue: hi + pad } }) });
    r.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 1 } }) });

    chartRef.current = chart;
    candles.current = c;
    riskStrip.current = r;
    marginLine.current = null;
    markers.current = createSeriesMarkers(c, []);

    const onClick = (p: MouseEventParams<Time>) => {
      if (useApp.getState().mode === "survive") return; // no scrubbing through a run
      if (p.logical === undefined || p.logical === null) return;
      const bucket = Math.min(nBuckets - 1, Math.max(0, Math.round(p.logical)));
      useTimeline.getState().seek(Math.min(n - 1, bucket * B + B - 1));
    };
    const onMove = (p: MouseEventParams<Time>) => {
      if (p.logical === undefined || p.logical === null || !p.point) return setHover(null);
      const bucket = Math.round(p.logical);
      if (bucket < 0 || bucket >= nBuckets) return setHover(null);
      const cur = Math.floor(useTimeline.getState().t);
      const first = bucket * B;
      if (first > cur) return setHover(null);
      setHover(aggregate(bundle, px, live, closedAt, first, Math.min(cur, first + B - 1, n - 1)));
    };
    chart.subscribeClick(onClick);
    chart.subscribeCrosshairMove(onMove);
    const onSize = () => setLayoutTick((v) => v + 1);
    chart.timeScale().subscribeSizeChange(onSize);
    return () => {
      chart.timeScale().unsubscribeSizeChange(onSize);
      chart.unsubscribeClick(onClick);
      chart.unsubscribeCrosshairMove(onMove);
      chart.remove();
      chartRef.current = null;
      marginLine.current = null;
    };
  }, [bundle, n, decimals, nBuckets, B, px, live, closedAt]);

  // Reveal candles up to the playhead; future buckets are whitespace so the time axis spans the storm.
  useEffect(() => {
    const c = candles.current;
    const r = riskStrip.current;
    if (!c || !r) return;
    const cd: (CandlestickData<Time> | WhitespaceData<Time>)[] = [];
    const rd: (HistogramData<Time> | WhitespaceData<Time>)[] = [];
    for (let k = 0; k < nBuckets; k++) {
      const first = k * B;
      const time = (bundle.t0 + first * bundle.step_s) as UTCTimestamp;
      if (first > frame) {
        cd.push({ time });
        rd.push({ time });
        continue;
      }
      const a = aggregate(bundle, px, live, closedAt, first, Math.min(frame, first + B - 1, n - 1));
      cd.push({ time, open: a.open, high: a.high, low: a.low, close: a.close });
      rd.push({ time, value: Math.max(0.04, a.maxRisk), color: a.closed ? CLOSED_COLOR : riskColor(a.maxRisk) });
    }
    c.setData(cd);
    r.setData(rd);
    const shown = allMarkers.filter((m) => m.i <= frame);
    markers.current?.setMarkers(shown.map((m) => m.m));
    // Keep the whole storm on the axis so candles draw in from left to right.
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: -0.5, to: nBuckets - 0.5 });

    // Marker labels: each sits over (or under) its candle; one that would touch a label already placed on that side
    // moves one line further out, so "Onset", "Squall" and "Alarm" in neighbouring candles stack instead of overlapping.
    // Laid out on the next animation frame: the chart has applied the new data and range by then, so its
    // coordinates are current (also on a paused first load, and after a resize: see layoutTick).
    const place = () => {
    const ts = chartRef.current?.timeScale();
    const host = el.current;
    const next: MarkerLabel[] = [];
    if (ts && host && host.clientWidth > 0) {
      const maxX = host.clientWidth - 62; // keep clear of the price axis
      // How many shapes each candle carries on each side: the label goes beyond that stack (about 13 px a shape).
      const perBar = new Map<string, number>();
      for (const mk of shown) {
        const key = `${Math.floor(mk.i / B)}${mk.m.position}`;
        perBar.set(key, (perBar.get(key) ?? 0) + 1);
      }
      const items: { mk: (typeof shown)[number]; above: boolean; cx: number; y: number; w: number }[] = [];
      for (const mk of shown) {
        const above = mk.m.position === "aboveBar";
        const bucket = Math.floor(mk.i / B);
        const first = bucket * B;
        const agg = aggregate(bundle, px, live, closedAt, first, Math.min(frame, first + B - 1, n - 1));
        const x = ts.timeToCoordinate(mk.m.time);
        const py = c.priceToCoordinate(above ? agg.high : agg.low);
        if (x === null || py === null) continue;
        const stack = perBar.get(`${bucket}${mk.m.position}`) ?? 1;
        const y = above ? py - 22 - stack * 13 : py + 10 + stack * 13;
        items.push({ mk, above, cx: x, y: Math.min(Math.max(y, 1), host.clientHeight - 72), w: mk.text.length * 6.1 + 6 });
      }
      items.sort((p, q) => p.cx - q.cx || p.mk.i - q.mk.i);
      // Labels on the same line that would touch push each other apart sideways, half the overlap each, so
      // "Onset", "Squall" and "Alarm" in the same or neighbouring candles read side by side around their markers.
      const clampX = (q: { cx: number; w: number }) => {
        q.cx = Math.min(Math.max(q.cx, q.w / 2 + 2), Math.max(q.w / 2 + 2, maxX - q.w / 2));
      };
      items.forEach(clampX);
      for (let pass = 0; pass < 40; pass++) {
        let moved = false;
        for (let a = 0; a < items.length; a++) {
          for (let b = a + 1; b < items.length; b++) {
            const p = items[a];
            const q = items[b];
            if (p.above !== q.above || Math.abs(p.y - q.y) >= LABEL_LINE) continue;
            const overlap = (p.w + q.w) / 2 + 3 - (q.cx - p.cx);
            if (overlap <= 0.01) continue;
            const dir = 1; // items are sorted by candle, then by time: the earlier event stays on the left
            p.cx -= (dir * overlap) / 2;
            q.cx += (dir * overlap) / 2;
            moved = true;
          }
        }
        items.forEach(clampX);
        if (!moved) break;
      }
      for (const it of items) next.push({ key: `${it.mk.i}-${it.mk.text}`, text: it.mk.text, color: it.mk.m.color, x: it.cx, y: it.y });
    }
    setLabels((prev) => (sameLabels(prev, next) ? prev : next));
    };
    const raf = requestAnimationFrame(place);
    return () => cancelAnimationFrame(raf);
  }, [frame, bundle, n, nBuckets, B, allMarkers, px, live, closedAt, layoutTick]);

  // Survive: the margin-call line, a red dashed price line. Off the chart when the line is outside the storm's price range.
  useEffect(() => {
    const c = candles.current;
    if (!c) return;
    const { lo, hi } = priceRange.current;
    const show = Number.isFinite(marginPrice) && marginPrice >= lo && marginPrice <= hi;
    if (show && !marginLine.current) {
      marginLine.current = c.createPriceLine({
        price: marginPrice,
        color: "#ff6b66",
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "Margin call",
      });
    } else if (show && marginLine.current) {
      marginLine.current.applyOptions({ price: marginPrice });
    } else if (!show && marginLine.current) {
      c.removePriceLine(marginLine.current);
      marginLine.current = null;
    }
  }, [marginPrice, bundle, n, nBuckets, B, px, live, closedAt, frame]);

  return (
    <div className={`panel chart ${large ? "large" : ""}`}>
      <div className="panel-head">
        <span>
          {bundle.symbol} · {B}-min candles
        </span>
        {live ? (
          <span className="chart-src" title={`Candles fetched from the live server (GET /api/candles), ${live.bucketFrames * bundle.step_s / 60}-minute bars`}>
            Tiger Data{live.queryMs !== null ? ` · ${live.queryMs < 10 ? live.queryMs.toFixed(1) : Math.round(live.queryMs)} ms` : ""}
          </span>
        ) : (
          <span className="muted">{bundle.title}</span>
        )}
      </div>
      <div className="chart-wrap">
        <div className="chart-host" ref={el} />
        <div className="chart-labels" aria-hidden="true">
          {labels.map((l) => (
            <span key={l.key} className="chart-label" style={{ left: l.x, top: l.y, color: l.color }}>
              {l.text}
            </span>
          ))}
        </div>
      </div>
      <div className="chart-foot">
        <span className="risk-key">risk strip</span>
        {hover ? (
          <span className="chart-tip">
            {fmtUtc(hover.time, false)} O {hover.open.toFixed(decimals)} H {hover.high.toFixed(decimals)} L {hover.low.toFixed(decimals)} C {hover.close.toFixed(decimals)}
            {showSpread ? ` · spread ${hover.meanSpread.toFixed(2)} bp` : ""}
            {hover.closed ? " · market closed" : ` · risk ${Math.round(hover.maxRisk * 100)}`}
          </span>
        ) : (
          <span className="muted">{survive ? "no seeking in Survive" : "click to seek"}</span>
        )}
      </div>
    </div>
  );
}
