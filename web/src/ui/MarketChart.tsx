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
  type IChartApi,
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
import { fmtUtc } from "../lib/format";

export const BUCKET = 5; // minutes per candle

interface BucketAgg {
  time: UTCTimestamp;
  first: number; // first frame
  open: number;
  high: number;
  low: number;
  close: number;
  maxRisk: number;
  meanSpread: number;
}

/** Aggregate one-minute bars into 5-minute candles, using frames first..upto (inclusive). */
function aggregate(b: Bundle, first: number, upto: number): BucketAgg {
  const s = b.series;
  let high = -Infinity;
  let low = Infinity;
  let maxRisk = 0;
  let spread = 0;
  for (let i = first; i <= upto; i++) {
    high = Math.max(high, s.high[i]);
    low = Math.min(low, s.low[i]);
    maxRisk = Math.max(maxRisk, s.risk[i]);
    spread += s.spread_bp[i];
  }
  return {
    time: (b.t0 + first * b.step_s) as UTCTimestamp,
    first,
    open: s.open[first],
    high,
    low,
    close: s.mid[upto],
    maxRisk,
    meanSpread: spread / (upto - first + 1),
  };
}

function riskColor(r: number): string {
  if (r >= 0.7) return "rgba(239, 83, 80, 0.9)";
  if (r >= 0.45) return "rgba(245, 166, 35, 0.85)";
  if (r >= 0.3) return "rgba(214, 196, 80, 0.7)";
  return "rgba(80, 160, 130, 0.55)";
}

const bucketTime = (b: Bundle, i: number) => (b.t0 + Math.floor(i / BUCKET) * BUCKET * b.step_s) as UTCTimestamp;

export function MarketChart({ bundle, derived, large = false }: { bundle: Bundle; derived: Derived; large?: boolean }) {
  const el = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const riskStrip = useRef<ISeriesApi<"Histogram"> | null>(null);
  const markers = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const frame = useFrameIndex();
  const [hover, setHover] = useState<BucketAgg | null>(null);
  const nBuckets = Math.ceil(derived.n / BUCKET);

  // All markers, revealed as the playhead passes them.
  const allMarkers = useMemo(() => {
    const out: { i: number; m: SeriesMarker<Time> }[] = [];
    out.push({
      i: bundle.storm.onset_i,
      m: { time: bucketTime(bundle, bundle.storm.onset_i), position: "aboveBar", shape: "circle", color: "#e0e6ee", text: "Onset" },
    });
    for (const e of bundle.events) {
      if (e.type === "alarm")
        out.push({ i: e.i, m: { time: bucketTime(bundle, e.i), position: "aboveBar", shape: "arrowDown", color: "#f5a623", text: "Alarm" } });
      if (e.type === "margin_call")
        out.push({ i: e.i, m: { time: bucketTime(bundle, e.i), position: "belowBar", shape: "square", color: "#ef5350", text: "Margin call" } });
    }
    out.sort((a, b) => a.i - b.i);
    return out;
  }, [bundle]);

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
      localization: { priceFormatter: (p: number) => p.toFixed(derived.priceDecimals) },
    });
    const c = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
      priceFormat: { type: "price", precision: derived.priceDecimals, minMove: Math.pow(10, -derived.priceDecimals) },
    });
    const r = chart.addSeries(HistogramSeries, { priceScaleId: "risk", priceLineVisible: false, lastValueVisible: false, base: 0 });
    chart.priceScale("risk").applyOptions({ scaleMargins: { top: 0.86, bottom: 0 }, visible: false });
    // Fix the price range to the whole storm so candles do not rescale as they are revealed.
    let lo = Infinity;
    let hi = -Infinity;
    for (let i = 0; i < derived.n; i++) {
      lo = Math.min(lo, bundle.series.low[i]);
      hi = Math.max(hi, bundle.series.high[i]);
    }
    const pad = (hi - lo) * 0.04;
    c.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: lo - pad, maxValue: hi + pad } }) });
    r.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 1 } }) });

    chartRef.current = chart;
    candles.current = c;
    riskStrip.current = r;
    markers.current = createSeriesMarkers(c, []);

    const onClick = (p: MouseEventParams<Time>) => {
      if (p.logical === undefined || p.logical === null) return;
      const bucket = Math.min(nBuckets - 1, Math.max(0, Math.round(p.logical)));
      useTimeline.getState().seek(Math.min(derived.n - 1, bucket * BUCKET + BUCKET - 1));
    };
    const onMove = (p: MouseEventParams<Time>) => {
      if (p.logical === undefined || p.logical === null || !p.point) return setHover(null);
      const bucket = Math.round(p.logical);
      if (bucket < 0 || bucket >= nBuckets) return setHover(null);
      const cur = Math.floor(useTimeline.getState().t);
      const first = bucket * BUCKET;
      if (first > cur) return setHover(null);
      setHover(aggregate(bundle, first, Math.min(cur, first + BUCKET - 1, derived.n - 1)));
    };
    chart.subscribeClick(onClick);
    chart.subscribeCrosshairMove(onMove);
    return () => {
      chart.unsubscribeClick(onClick);
      chart.unsubscribeCrosshairMove(onMove);
      chart.remove();
      chartRef.current = null;
    };
  }, [bundle, derived, nBuckets]);

  // Reveal candles up to the playhead; future buckets are whitespace so the time axis spans the storm.
  useEffect(() => {
    const c = candles.current;
    const r = riskStrip.current;
    if (!c || !r) return;
    const cd: (CandlestickData<Time> | WhitespaceData<Time>)[] = [];
    const rd: (HistogramData<Time> | WhitespaceData<Time>)[] = [];
    for (let k = 0; k < nBuckets; k++) {
      const first = k * BUCKET;
      const time = (bundle.t0 + first * bundle.step_s) as UTCTimestamp;
      if (first > frame) {
        cd.push({ time });
        rd.push({ time });
        continue;
      }
      const a = aggregate(bundle, first, Math.min(frame, first + BUCKET - 1, derived.n - 1));
      cd.push({ time, open: a.open, high: a.high, low: a.low, close: a.close });
      rd.push({ time, value: Math.max(0.04, a.maxRisk), color: riskColor(a.maxRisk) });
    }
    c.setData(cd);
    r.setData(rd);
    markers.current?.setMarkers(allMarkers.filter((m) => m.i <= frame).map((m) => m.m));
    // Keep the whole storm on the axis so candles draw in from left to right.
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: -0.5, to: nBuckets - 0.5 });
  }, [frame, bundle, derived, nBuckets, allMarkers]);

  return (
    <div className={`panel chart ${large ? "large" : ""}`}>
      <div className="panel-head">
        <span>
          {bundle.symbol} · {BUCKET}-min candles
        </span>
        <span className="muted">{bundle.title}</span>
      </div>
      <div className="chart-host" ref={el} />
      <div className="chart-foot">
        <span className="risk-key">risk strip</span>
        {hover ? (
          <span className="chart-tip">
            {fmtUtc(hover.time, false)} O {hover.open.toFixed(derived.priceDecimals)} H {hover.high.toFixed(derived.priceDecimals)} L{" "}
            {hover.low.toFixed(derived.priceDecimals)} C {hover.close.toFixed(derived.priceDecimals)} · spread {hover.meanSpread.toFixed(2)} bp · risk{" "}
            {Math.round(hover.maxRisk * 100)}
          </span>
        ) : (
          <span className="muted">click to seek</span>
        )}
      </div>
    </div>
  );
}
