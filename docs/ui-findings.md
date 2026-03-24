# UI, Accessibility & UX Findings

Automated frontend review conducted 2026-03-23. Issues are ordered by severity.
No code has been changed — this document tracks issues for future remediation.

---

## High Severity

### H1 — No ARIA Live Region for SSE Progress Updates
**Files:** `frontend/src/components/ProgressStepper.tsx` (line ~77), `frontend/src/pages/ReportPage.tsx` (lines ~57–68)

When a user submits a URL, the progress stepper and stage message update dynamically via SSE.
There is no `aria-live` region announcing these changes to screen readers. A user relying on
assistive technology submits the form and receives no feedback that analysis is running or
that it has completed.

**Fix:** Add `role="status"` and `aria-live="polite"` to the stage message paragraph in
`ProgressStepper.tsx`. Add `role="alert"` and `aria-live="assertive"` to the error and warning
banners in `ReportPage.tsx`.

---

### H2 — Error and Warning Banners Have No `role="alert"`
**File:** `frontend/src/pages/ReportPage.tsx` (lines ~41–54)

The error (`XCircle`) and warning (`AlertTriangle`) banners are plain `<div>` elements with no
`role="alert"` or `aria-live="assertive"`. Screen reader users who get a scraping error or
invalid URL message receive no announcement.

**Fix:**
```tsx
<div role="alert" aria-live="assertive" className="...">
  {/* error content */}
</div>
```

---

### H3 — Progress Bar Lacks ARIA Semantics
**File:** `frontend/src/components/ProgressStepper.tsx` (lines ~79–83)

```tsx
<div className="mt-2 w-full bg-gray-800 rounded-full h-2">
  <div
    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
    style={{ width: `${Math.min((progress / total) * 100, 100)}%` }}
  />
</div>
```

The `<div>` acting as a progress bar has no `role="progressbar"`, no `aria-valuenow`,
`aria-valuemin`, `aria-valuemax`, or `aria-label`. It is completely invisible to assistive
technology.

**Fix:**
```tsx
<div
  role="progressbar"
  aria-valuenow={Math.min(Math.round((progress / total) * 100), 100)}
  aria-valuemin={0}
  aria-valuemax={100}
  aria-label="Analysis progress"
  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
  style={{ width: `${Math.min((progress / total) * 100, 100)}%` }}
/>
```

---

### H4 — Aspect Toggle Buttons Have No `aria-pressed` State
**File:** `frontend/src/components/UrlInput.tsx` (lines ~83–95)

The aspect toggle buttons change visual appearance when selected, but have no `aria-pressed`
attribute. Screen readers cannot tell users which aspects are currently active. Additionally,
when no aspects are selected, the submit button becomes disabled but no accessible error message
explains why.

**Fix:** Add `aria-pressed={selectedAspects.includes(aspect)}` to each toggle button. Add an
`aria-describedby` pointing to a helper text element when no aspects are selected.

---

### H5 — Decorative Search Icon Not Hidden from Assistive Technology
**File:** `frontend/src/components/UrlInput.tsx` (line ~63)

The `<Search>` Lucide icon inside the URL input container is a purely decorative visual
affordance. Without `aria-hidden="true"`, screen readers may announce it as "search" or read
its SVG path, creating noise.

**Fix:** Add `aria-hidden="true"` to the icon:
```tsx
<Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" aria-hidden="true" />
```

---

### H6 — Stale Closure Risk in `handleEvent` / `useCallback` Pattern
**File:** `frontend/src/hooks/useSSE.ts` (lines ~117–181)

`handleEvent` is defined as a plain function inside the hook body (not wrapped in `useCallback`).
`startReport` captures it via closure with a `[]` dependency array. Since `startReport` captures
the first-render version of `handleEvent`, if `handleEvent` ever reads from state directly
(rather than using the functional `prev =>` updater form), it would observe stale state.

**Fix:** Either move `handleEvent` inside `startReport`'s callback body (so it always has fresh
closure), or wrap it in `useCallback` with the appropriate dependencies.

---

### H7 — `cancel()` Does Not Reset UI State
**File:** `frontend/src/hooks/useSSE.ts` (lines ~183–188)

`cancel()` aborts the fetch and sets `isRunning = false`, but leaves `stage`, `stageMessage`,
`distributions`, `report`, and other state at whatever mid-stream values they held. After
cancelling, the page retains partial charts and an incomplete progress stepper with no message
indicating the operation was cancelled.

**Fix:** Call `setState(initialState)` inside `cancel()` after aborting, and add a brief visual
indicator (e.g., a toast or banner: "Analysis cancelled").

---

## Medium Severity

### M1 — `formatAspect` Utility Duplicated Across Four Files
**Files:**
- `frontend/src/components/UrlInput.tsx` (line ~43)
- `frontend/src/components/report/AspectSection.tsx` (line ~9)
- `frontend/src/components/charts/SentimentBarChart.tsx` (line ~17)
- `frontend/src/components/charts/AspectRadarChart.tsx` (line ~16)

An identical `formatAspect` function (replacing underscores with spaces, title-casing) is
copy-pasted into every component that uses it.

**Fix:** Extract to `frontend/src/utils/format.ts` and import from there.

---

### M2 — No Explanation When Submit Button Is Disabled Due to No Aspects
**File:** `frontend/src/components/UrlInput.tsx` (lines ~100–113)

When no aspects are selected, the submit button becomes disabled with no visible message
explaining why. The disabled state for "no aspects selected" is visually identical to the
disabled state for "invalid URL", giving the user no indication of what to fix.

**Fix:** Add an inline helper text below the aspect buttons:
```tsx
{selectedAspects.length === 0 && (
  <p className="text-xs text-red-400 mt-1">Select at least one aspect to analyze.</p>
)}
```

---

### M3 — Charts Have No Accessible Alternative
**Files:** `frontend/src/components/charts/SentimentBarChart.tsx`, `SentimentPieChart.tsx`, `AspectRadarChart.tsx`

All three Recharts visualizations render SVG with no accessible text alternative: no `aria-label`
on the `ResponsiveContainer`, no visually-hidden data table, and no `<title>`/`<desc>` inside
the SVG. Colorblind users and screen reader users cannot access any quantitative chart data.

**Fix:** Add `aria-label` to each chart container describing its content, and add a visually
hidden `<table>` (using a `sr-only` class) with the same data for screen readers.

---

### M4 — Pie Chart Title Is Misleading
**File:** `frontend/src/pages/ReportPage.tsx` (line ~97), `frontend/src/components/charts/SentimentPieChart.tsx`

The card header says "Mentioned Sentiment" and the subtitle says "Among reviews that mentioned
each aspect." The pie chart actually aggregates mention counts across ALL aspects, which
double-counts reviews that mention multiple aspects. A single review contributes to multiple
wedges.

**Fix:** Update the chart title and subtitle to accurately describe the aggregation (e.g.,
"Aggregate Aspect Mentions" with a note explaining double-counting), or recompute the chart
to show unique-review sentiment instead.

---

### M5 — `movieTitle` State Is Dead Code
**Files:** `frontend/src/hooks/useSSE.ts` (line ~127), `frontend/src/pages/ReportPage.tsx`

`useSSE` accumulates `movieTitle` from SSE stage events and returns it in its state object.
`ReportPage` never reads `sse.movieTitle` — it reads `sse.report?.movie_title` instead.
`movieTitle` in the hook is redundant dead state.

**Fix:** Remove the `movieTitle` field from the hook's state and return value.

---

### M6 — `completedAspects` Not Cleaned Up After Final Report Arrives
**File:** `frontend/src/hooks/useSSE.ts` (lines ~131–135)

`completedAspects` is used as a fallback display before the final `report` event, but once
the `report` event fires, `completedAspects` becomes dead data that is never cleared.
A subsequent `startReport` call resets it, but it persists in memory unnecessarily.

**Fix:** Clear `completedAspects` (set to `[]`) when the `report` event is handled.

---

### M7 — No SSE Stream Timeout or Hung-State Detection
**File:** `frontend/src/hooks/useSSE.ts` (line ~82)

The `while (true)` loop reading from the SSE stream will block indefinitely if the backend
hangs or the network drops. The user sees a perpetually spinning stepper with no recourse
except manually clicking "Cancel" (which doesn't communicate that it was cancelled, see H7).

**Fix:** Implement a client-side heartbeat timeout: if no SSE event is received within
a configurable window (e.g., 60 seconds), automatically cancel and display a timeout message.

---

### M8 — Stacked Bar Chart Visual Bug: Inconsistent Border Radius
**File:** `frontend/src/components/charts/SentimentBarChart.tsx` (lines ~58–59)

`<Bar dataKey="Positive">` has `radius={[0, 0, 0, 0]}` while `<Bar dataKey="Negative">` has
`radius={[4, 4, 0, 0]}`. Since bars are stacked (Negative on top), if any negative value
exists the top of the bar gets rounded corners. If positive is 100%, the bar has square corners.
The result looks visually inconsistent.

**Fix:** Apply rounding only to the outermost bar (the one on top in the stack), or use
`radius={[4, 4, 0, 0]}` on the Positive bar and `radius={[0, 0, 0, 0]}` on Negative, since
Positive is at the base and Negative is the cap.

---

### M9 — Mini Bar in `AspectSection` Has No "Not Mentioned" Legend
**File:** `frontend/src/components/report/AspectSection.tsx` (lines ~60–73)

The horizontal mini bar renders green for positive % and red for negative %, but the gray
remainder (representing "not mentioned" reviews) has no label or legend. Users unfamiliar with
the UI will not know what the empty gray portion represents.

**Fix:** Add a small legend below the bar, or a tooltip, explaining the three segments:
Positive / Negative / Not mentioned.

---

### M10 — Array Index Used as `key` in Quote Map
**File:** `frontend/src/components/report/AspectSection.tsx` (line ~89)

```tsx
{aspect.top_quotes.slice(0, 3).map((q, i) => (
  <blockquote key={i} ...>
```

Using array index as React `key` is an anti-pattern that can cause incorrect reconciliation
if items reorder or filter.

**Fix:** Use a stable identifier — either a hash of the quote string, or the quote text itself
(truncated) as the key, since quotes are stable server-provided data.

---

### M11 — "Top Quotes" Label Shows Total Review Count, Not Quote Count
**File:** `frontend/src/components/report/AspectSection.tsx` (line ~85)

```tsx
<p className="...">Top Quotes ({total} reviews)</p>
```

`total` is the total number of reviews analyzed for that aspect (positive + negative +
not_mentioned), not the number of quotes being displayed (always 3 or fewer). A label reading
"Top Quotes (87 reviews)" looks like it's showing 87 quotes.

**Fix:** Change the label to clarify: `"Top Quotes"` with a separate note like
`"from {total} reviews analyzed"`, or show just the quote count.

---

## Low Severity

### L1 — Unused Scaffold Assets in `src/assets/`
**Files:** `frontend/src/assets/react.svg`, `frontend/src/assets/vite.svg`, `frontend/src/assets/hero.png`

Default Vite scaffold files `react.svg` and `vite.svg` are never imported. `hero.png` also
appears unused.

**Fix:** Delete these files.

---

### L2 — URL Input Uses `type="text"` Instead of `type="url"`
**File:** `frontend/src/components/UrlInput.tsx` (line ~55)

`type="url"` gives mobile users the correct keyboard layout (with `.com`, `/` keys) and
provides a semantic hint to browsers and assistive technology.

**Fix:** Change `type="text"` to `type="url"` on the IMDB URL input.

---

### L3 — URL Input Has No `autoComplete` Attribute
**File:** `frontend/src/components/UrlInput.tsx` (line ~55)

Without an explicit `autoComplete` attribute, browser behaviour is undefined (it may offer
password autofill incorrectly).

**Fix:** Add `autoComplete="url"` (or `"off"` if autocomplete is not desired).

---

### L4 — `ProgressStepper` Breaks on Narrow Screens
**File:** `frontend/src/components/ProgressStepper.tsx` (lines ~29–72)

The stepper uses `flex items-center justify-between` with full-width step labels. On screens
narrower than ~400px, the labels ("Scraping Reviews", "Analyzing Sentiment", "Generating
Report") overflow or get truncated with no responsive fallback.

**Fix:** Add `sm:` breakpoint variants to hide or abbreviate labels on small screens, or
switch to a vertical stepper layout on mobile.

---

### L5 — No "Analysis Complete" Message When Stepper Reaches Done State
**Files:** `frontend/src/pages/ReportPage.tsx` (line ~15), `frontend/src/components/ProgressStepper.tsx`

`showProgress` remains `true` when `stage === 'done'`, so the stepper stays visible with all
three green checkmarks. But `stageMessage` in the done state will show whatever the last
message was (e.g., "Generating Report..."), which looks like the operation is still running.

**Fix:** Emit a final `stageMessage` of "Analysis complete!" in the `done` SSE event handler,
or hide the stepper and show a dedicated completion banner.

---

### L6 — `SentimentPieChart` Renders Blank SVG When All Values Are Zero
**File:** `frontend/src/components/charts/SentimentPieChart.tsx` (line ~26)

When all aspect sentiment values are zero (e.g., no reviews matched), `data` is filtered to
an empty array and the chart renders a blank 300px-tall SVG with no user feedback.

**Fix:** Add an empty-state guard:
```tsx
if (data.length === 0) {
  return <p className="text-gray-500 text-sm text-center py-8">No data to display.</p>;
}
```

---

### L7 — Radar Chart Axis Has No Unit Label
**File:** `frontend/src/components/charts/AspectRadarChart.tsx`

The `PolarRadiusAxis` shows tick values 0–100 without a unit. The `Tooltip` formats them as
`${value}%`, but users cannot tell what the 0–100 scale means from the axis alone (it is
% of mentioned reviews that are positive).

**Fix:** Add a unit label to the axis or update the chart title/subtitle to include the
definition inline.

---

### L8 — No Design Token System / Theme Documentation
**File:** `frontend/src/index.css` (line 1)

Tailwind v4 is used with `@import "tailwindcss"` and no `tailwind.config.js`. There is no
documented color palette, spacing scale, or typography system. Dark-mode classes (`gray-950`,
`gray-900`, etc.) are used directly without abstraction.

**Fix:** Create a `tailwind.config.js` (or use v4's CSS variable theme approach) to define a
brand color palette and document intentional design decisions.

---

### L9 — `Card` Component `className` Concatenation Has Trailing Space Risk
**File:** `frontend/src/components/ui/Card.tsx` (lines ~10, 18, 25)

All three `Card` variants concatenate `className` via template literal:
```tsx
className={`bg-gray-900 ... ${className}`}
```

When `className` is `''` (the default), this produces a trailing space. While harmless in
browsers, it is imprecise and will generate linting warnings.

**Fix:** Use `clsx` or a `cn` utility to merge class names safely.

---

### L10 — Non-Null Assertion on `getElementById` in `main.tsx`
**File:** `frontend/src/main.tsx` (line 6)

```tsx
createRoot(document.getElementById('root')!).render(...)
```

The `!` bypasses TypeScript's null check. If the `#root` element is missing, this throws an
unhandled runtime error with a confusing stack trace.

**Fix:**
```tsx
const root = document.getElementById('root');
if (!root) throw new Error('Root element #root not found in index.html');
createRoot(root).render(<App />);
```

---

### L11 — `reset` From `useSSE` Is Never Called; No "Clear Results" Button
**Files:** `frontend/src/hooks/useSSE.ts` (line ~41), `frontend/src/pages/ReportPage.tsx`

`reset` is returned from `useSSE` but `ReportPage` never calls it. There is no "clear results"
button. Users cannot reset to a clean state without submitting a new URL (which does reset
state on `startReport`) or refreshing the page.

**Fix:** Add a "Clear / Start Over" button that calls `reset()` and scrolls back to the input.
Or remove `reset` from the hook's return value if it is intentionally unused.

---

### L12 — No Meaningful `<title>` or `<meta description>` in HTML Template
**File:** `index.html` (Vite scaffold default)

The application likely still has the default Vite page title ("Vite + React" or similar) and
no `<meta name="description">`. This affects browser tab labeling, bookmarks, social sharing,
and SEO.

**Fix:** Update `index.html`:
```html
<title>Movie Review Sentiment Analyzer</title>
<meta name="description" content="Analyze IMDB movie reviews by sentiment across aspects like acting, plot, and pacing." />
```
