import type { Inspector, Report } from "../types/bundle";

/** The inspector's verdict: "ok" or "flag" from the backend; anything else is shown as it came. */
export function InspectorLine({ inspector }: { inspector: Inspector }) {
  const v = inspector.verdict.toLowerCase();
  const ok = v === "ok" || v === "pass";
  const flag = v === "flag" || v === "fail";
  return (
    <div className={`inspector ${ok ? "ok" : flag ? "flag" : ""}`}>
      <div className="inspector-verdict">
        {ok && "Inspector: no issues found"}
        {flag && `Inspector flagged ${inspector.issues.length || "an"} issue${inspector.issues.length === 1 ? "" : "s"}`}
        {!ok && !flag && `Inspector: ${inspector.verdict}`}
      </div>
      {inspector.issues.length > 0 && (
        <ul>
          {inspector.issues.map((x, k) => (
            <li key={k}>{x}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function VerifiedBadge({ verified, unverified }: { verified: boolean; unverified: unknown[] }) {
  if (verified && unverified.length === 0) return <span className="badge verified">numbers checked by code</span>;
  return (
    <span className="badge warn" title={unverified.map(String).join(", ")}>
      {unverified.length > 0 ? `${unverified.length} number${unverified.length === 1 ? "" : "s"} not verified` : "numbers not verified"}
    </span>
  );
}

/** Report text, a badge when code verified every number, and the inspector's verdict. */
export function ReportBody({ report }: { report: Report }) {
  const paragraphs = report.text
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
  return (
    <>
      <div className="badges">
        <VerifiedBadge verified={report.verified} unverified={report.unverified_numbers} />
      </div>
      {!report.verified && report.unverified_numbers.length > 0 && (
        <div className="report-unverified">Not matched to the data: {report.unverified_numbers.map(String).join(", ")}</div>
      )}
      <div className="report-text">
        {paragraphs.map((p, k) => (
          <p key={k}>{p}</p>
        ))}
      </div>
      {report.inspector && <InspectorLine inspector={report.inspector} />}
      {report.model && <div className="report-model">written by: {report.model}</div>}
    </>
  );
}

/**
 * The storm report now lives in the right column's card, under its "Report" tab (ui/Manifest.tsx), collapsed at
 * first. App.tsx still mounts this standalone panel; it renders nothing so the report is not shown twice.
 * Kamil / the App.tsx owner can drop the mount at the next merge.
 */
export function ReportPanel(_props: { report: Report | null }) {
  return null;
}
