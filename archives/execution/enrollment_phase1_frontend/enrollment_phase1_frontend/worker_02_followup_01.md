Codex targeted same-session remediation:

Actual CSS audit found `max-width: 1400px` in `today.css` and `max-width: 1600px` in `board.css`, which recreates wide-screen blank space.

1. Remove page content width caps so both pages consume all AppShell content width at 1920 and at 200% zoom without page-level horizontal overflow. Keep only component-local overflow for the dense matrix.
2. Replace the hand-drawn common shell icons with `lucide-react` icons per project frontend rules. First verify the current pinned version and MIT license, install the exact dependency, use familiar icons with Chinese accessible names/tooltips, and remove obsolete icon code.
3. Add or adjust tests for absence of page max-width caps and icon accessibility.
4. Run `npm test` and `npm run build`.

Stay inside worker 02's authorized write set. Report exact changes and results using the original execution output schema.
