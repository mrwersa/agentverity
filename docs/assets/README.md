# Figures

Each diagram keeps its source beside the rendered image. The source is what
gets reviewed and diffed; a raster render exists only where the publishing
surface cannot handle the source, which for Mermaid means anywhere outside
GitHub.

Regenerate a Mermaid figure after editing its `.mmd`:

```bash
npx @mermaid-js/mermaid-cli -i docs/assets/<name>.mmd -o docs/assets/<name>.png -w 1200 -b white
```

## What each file is for

Grep will tell you that some of these are referenced nowhere in this
repository. That does not make them unused. Several are fetched over HTTP by
the published article through URLs pinned to the commit that introduced them,
so nothing here mentions them and deleting them looks free. It is not free:
the pinned URL survives, because the blob stays reachable through history, but
the working copy needed to render a revision would be gone.

| file | used by |
|---|---|
| `evidence-by-route.mmd` / `.png` | The article. The `.mmd` records the semantic source and the PNG follows the article house style. |
| `agentcore-release-gate.svg` | This repository's README, directly. |
| `agentcore-release-gate.png` | The article. Raster because Medium does not take SVG. |
| `diagnostic-report.svg` | `docs/integrations.md`, directly. |
| `evidence-gate-comparison.png` | The article. |
| `payment-router-overview.png` | The article. |
