# browser-screenshot

A Claude Code skill that screenshots web pages in your real Chrome through the Claude in Chrome extension: the current view, one section, or the full page, at desktop (1920), tablet (768) or mobile (393) width.

## Install

Lives in the opstack repo as a submodule at `skills/browser-screenshot`; `~/.claude/skills` points at `opstack/skills`, so there is nothing to install. To use it standalone, clone `https://github.com/derek98765/browser-screenshot.git` into `~/.claude/skills/browser-screenshot`.

`scripts/stitch.py` (full-page tiles) needs Pillow (`pip3 install pillow`).
