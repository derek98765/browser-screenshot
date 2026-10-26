---
name: browser-screenshot
description: Screenshot a web page in the user's real Chrome via the Claude for Chrome extension — the current view, one section/element, or the full scrollable page — at desktop (1920), tablet (768) or mobile (393) width. Chrome-only; never agent-browser, Playwright or headless browsers. Use whenever the user asks to "take a screenshot", "screenshot this page/section", "full page screenshot", "capture at mobile/tablet/desktop", or "save screenshots to <folder>".
---

# Take a screenshot

Speed matters: plan the whole capture up front and use `browser_batch` to run scroll + screenshot steps in **one** call instead of one round trip per step.

## 1. Setup

1. Load the Chrome tools in one `ToolSearch` call: `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__tabs_close_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__resize_window,mcp__claude-in-chrome__browser_batch`.
2. `tabs_context_mcp` with `createIfEmpty: true`, then open a new tab and `navigate` to the URL. If the tools aren't available or Chrome isn't connected, stop and ask the user to connect Claude in Chrome (terminal: `/chrome`). Don't fall back to another browser.
3. Do any setup the user asked for (click a tab, open a menu) before capturing.

## 2. Width

Default is **desktop only** unless the user names other sizes.

| Size | Width | Height (iframe) | How |
|---|---|---|---|
| Desktop | 1920 | — | `resize_window` 1920 wide, then check `innerWidth` with JS. The resize can apply late, so re-check once before giving up. |
| Tablet | 768 | 1024 | iframe, as below |
| Mobile | 393 | 852 | iframe, as below |

**Tablet/mobile: never resize the window.** Chrome has a minimum width, and media queries follow the window, not a wrapper. Load the page in a same-origin iframe of the target width instead:

```js
const W = 393, H = Math.min(852, innerHeight);   // must fit in the window
const f = document.createElement('iframe');
f.id = '__shot'; f.src = location.href;
f.style.cssText = `position:fixed;top:0;left:0;width:${W}px;height:${H}px;border:0;z-index:2147483647;background:#fff`;
document.body.appendChild(f);
await new Promise(r => f.onload = r); await new Promise(r => setTimeout(r, 2500));
f.contentWindow.innerWidth
```

Run every later step against `f.contentDocument` / `f.contentWindow`. When you're done, remove it with `document.getElementById('__shot').remove()`.

## 3. Capture

**Capture with `computer` → `zoom`, not `screenshot`.** `screenshot` is capped at about 1568px wide and saved as a JPEG, so a 1920 page comes back blurry. `zoom` saves a native 1:1 PNG as long as the region is no wider than about 1500px. Its `region` is `[x0, y0, x1, y1]` in CSS px of the viewport. So:

- Region ≤ 1500px wide: one `zoom`.
- Wider (a desktop row): two zooms, `[0, y0, 960, y1]` and `[960, y0, cw, y1]`.

Always pass `save_to_disk: true` and **never pass `scale`**, because it shrinks the saved file. Before capturing, `hover` a spot outside the region, because the cursor shows up in zooms.

- **Current view:** zoom the whole viewport (two halves on desktop), then stitch at y=0.
- **Section/element:** run `el.scrollIntoView({block:'center'})` and read `getBoundingClientRect()`. Zoom `[x-16, y-16, right+16, bottom+16]`. The saved PNG is the final image, so just copy it to the output path.
- **Full page:** the extension can only capture the viewport, so capture tiles and stitch them. Prep the page and get the offsets in one JS call:

```js
const d = document, w = window;              // use the iframe's doc/window for tablet/mobile
d.querySelectorAll('*').forEach(el => {
  const p = getComputedStyle(el).position;
  if (p === 'sticky') el.style.position = 'static';
  else if (p === 'fixed') el.tagName === 'NAV' || el.querySelector('nav')
    ? el.style.position = 'absolute'          // keep the header once, at the top
    : el.style.visibility = 'hidden';         // floating buttons, widgets
});
const H = () => d.documentElement.scrollHeight;
for (let y = 0; y < H(); y += 600) { w.scrollTo(0, y); await new Promise(r => setTimeout(r, 150)); }
w.scrollTo(0, 0); await new Promise(r => setTimeout(r, 400));
const vh = w.innerHeight, h = H(), offs = [];
for (let y = 0; y < h - vh; y += vh) offs.push(y);
offs.push(h - vh);
JSON.stringify({ h, vh, cw: d.documentElement.clientWidth, vw: innerWidth, offs })
```

Then capture every tile in **one `browser_batch`**. For each offset, add a `javascript_tool` item that runs `scrollTo(0, <off>); await new Promise(r=>setTimeout(r,300)); scrollY`, followed by the zoom item(s) for that row, each over `[x0, 0, x1, vh]`. Stitch, giving each tile's region left edge and scroll offset:

```bash
python3 scripts/stitch.py out.png <cw> <h> a0.png:0,0 b0.png:960,0 a1.png:0,<off1> b1.png:960,<off1> ...
```

(`cw` is the content width without the scrollbar. For an iframe, it's the device width, with one tile per row at x=0.)

## 4. Finish

- Save to the folder the user named (default `~/Downloads`), named like `<page>-<section?>-<size>-<YYYYMMDD-HHMMSS>.png`.
- Remove the iframe, or reload the page if you flattened it, and close the tab you opened.
- `Read` one image so the user sees it, and report the real dimensions.
