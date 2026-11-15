// When the app opens on the landing page, and how the address bar follows it. No imports, so state/app.ts can use it.

/** The landing page opens when the URL names neither a storm nor a mode. */
export function landingFromUrl(search: string = typeof window === "undefined" ? "" : window.location.search): boolean {
  try {
    const p = new URLSearchParams(search);
    return !p.has("storm") && !p.has("mode");
  } catch {
    return false;
  }
}

/** Set (string) or drop (null) ?storm= and ?mode=; ?at= always goes. Other parameters stay. */
export function setLandingUrl(params: { storm?: string | null; mode?: string | null }) {
  try {
    const url = new URL(window.location.href);
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined) continue;
      if (v === null) url.searchParams.delete(k);
      else url.searchParams.set(k, v);
    }
    url.searchParams.delete("at");
    window.history.replaceState(null, "", url);
  } catch {
    /* no history API: the page still changes */
  }
}
