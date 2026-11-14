/** ?hide=sky,clouds,sea,lighthouse,lhbeam,... leaves scene parts out (for finding a rendering fault on a real GPU). */
const HIDE = (() => {
  try {
    return new Set((new URLSearchParams(window.location.search).get("hide") ?? "").split(",").filter(Boolean));
  } catch {
    return new Set<string>();
  }
})();
export const show = (name: string) => !HIDE.has(name);
