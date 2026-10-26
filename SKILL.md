---
name: browser-screenshot
description: Screenshot a web page in the user's real Chrome via the Claude for Chrome extension — the current view, one section/element, or the full scrollable page — at desktop (1920), tablet (768) or mobile (393) width. Chrome-only; never agent-browser, Playwright or headless browsers. Use whenever the user asks to "take a screenshot", "screenshot this page/section", "full page screenshot", "capture at mobile/tablet/desktop", or "save screenshots to <folder>".
---

# Browser screenshot

Speed comes from **few round trips**. Every response you wait on costs seconds, so follow this exact five-step flow and put everything else inside `browser_batch`:

1. `ToolSearch`: load the tools
2. `navigate`: open the page
3. batch: prepare and measure
4. batch: capture and close the tab
5. `Bash`: save or stitch

Don't ask questions you can default (size defaults to desktop, folder to `~/Downloads`). Don't `Read` the result afterwards, because the zoom image already shows in the chat.

## 1. Load the tools

One call: `select:mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__browser_batch,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__resize_window,mcp__claude-in-chrome__tabs_close_mcp,mcp__claude-in-chrome__tabs_context_mcp`.

If the tools aren't there or Chrome isn't connected, stop and ask the user to connect Claude in Chrome. Never fall back to another browser.

## 2. Open the page

Call `navigate` **standalone, without `tabId`**. It creates this session's tab group and tab by itself and returns the `tabId`. No separate `tabs_context_mcp` or `tabs_create_mcp` call is needed.

## 3. Prepare and measure (one batch)

| Size | Width | How |
|---|---|---|
| Desktop (default) | 1920 | `resize_window` 1920×1050 as the batch's first item |
| Tablet | 768 | iframe, no resize |
| Mobile | 393 | iframe, no resize |

Never resize for tablet or mobile. Chrome has a minimum window width, and media queries follow the window. Use a same-origin iframe instead.

Put one `javascript_tool` item after the resize. It waits for readiness (not a fixed sleep), does any setup the user asked for (clicking a tab, opening a menu), and returns everything step 4 needs:

```js
const until = async (f, ms = 3000) => { const t = Date.now(); while (!f() && Date.now() - t < ms) await new Promise(r => setTimeout(r, 100)); };
const ready = d => d.readyState === 'complete' && [...d.images].every(i => i.complete);
await until(() => ready(document) && innerWidth === 1920);   // desktop; the resize can apply late
// --- tablet/mobile instead: mount the page in an iframe ---
// const W = 393, H = Math.min(852, innerHeight), f = document.createElement('iframe');
// f.id = '__shot'; f.src = location.href;
// f.style.cssText = `position:fixed;top:0;left:0;width:${W}px;height:${H}px;border:0;z-index:2147483647;background:#fff`;
// document.body.appendChild(f); await new Promise(r => f.onload = r); await until(() => ready(f.contentDocument));
// ...then use f.contentDocument / f.contentWindow as d / w below
// --- setup, e.g. a Radix tab or menu (they open on pointerdown) ---
// el.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})); el.click(); await new Promise(r => setTimeout(r, 400));
// --- target ---
const el = document.querySelector('<selector>');
el.scrollIntoView({ block: 'center' }); await new Promise(r => setTimeout(r, 300));
const r = el.getBoundingClientRect();
JSON.stringify({ vw: innerWidth, vh: innerHeight, x: r.x, y: r.y, right: r.right, bottom: r.bottom })
```

If `vw` comes back wrong, re-check once in the next batch before reporting.

**Full page:** replace the target part with this prep. It flattens sticky and fixed elements, plays scroll-reveal animations, and returns the tile offsets:

```js
const d = document, w = window;
d.querySelectorAll('*').forEach(e => { const p = getComputedStyle(e).position;
  if (p === 'sticky') e.style.position = 'static';
  else if (p === 'fixed') (e.tagName === 'NAV' || e.querySelector('nav')) ? e.style.position = 'absolute' : e.style.visibility = 'hidden'; });
const H = () => d.documentElement.scrollHeight;
for (let y = 0; y < H(); y += 800) { w.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); }
w.scrollTo(0, 0); await new Promise(r => setTimeout(r, 300));
const vh = w.innerHeight, h = H(), offs = [];
for (let y = 0; y < h - vh; y += vh) offs.push(y); offs.push(Math.max(0, h - vh));
JSON.stringify({ h, vh, cw: d.documentElement.clientWidth, offs })
```

## 4. Capture and close (one batch)

**Capture with `computer` → `zoom`, never `screenshot`.** `screenshot` is capped at about 1568px wide and saved as a JPEG, so it comes out blurry. `zoom` saves a native 1:1 PNG for regions up to about 1500px wide. `region` is `[x0, y0, x1, y1]` in CSS px and must stay inside the viewport. Always pass `save_to_disk: true`, and never pass `scale`.

The batch is:

1. `hover` a spot outside the region, so the cursor isn't in the shot
2. the zoom(s)
3. `tabs_close_mcp`

What to zoom:

- **Section/element:** one zoom over `[x-16, y-16, right+16, bottom+16]`.
- **Current view:** the viewport, as two halves on desktop: `[0,0,960,vh]` and `[960,0,1920,vh]`.
- **Full page:** for each offset, a `javascript_tool` item `scrollTo(0, <off>); await new Promise(r => setTimeout(r, 250)); scrollY`, then that row's zoom(s) over `[0,0,960,vh]` and `[960,0,cw,vh]`. For an iframe, scroll `document.getElementById('__shot').contentWindow` and use one zoom per row, `[0,0,W,vh]`.

## 5. Save (one Bash call)

Name files `<page>-<section?>-<size>-<YYYYMMDD-HHMMSS>.png` in the folder the user named, or `~/Downloads`.

- **Single zoom:** `cp` the saved PNG to the output path.
- **Tiles:** stitch them, giving each tile's region left edge and scroll offset:

```bash
python3 ~/.claude/skills/browser-screenshot/scripts/stitch.py OUT.png <cw> <h> a0.png:0,0 b0.png:960,0 a1.png:0,<off1> b1.png:960,<off1> ...
```

Report each file's path and its real dimensions.
