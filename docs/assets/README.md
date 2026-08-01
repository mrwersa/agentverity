# Figures

Each diagram keeps its Mermaid source beside the rendered image. The source is
what gets reviewed and diffed; the PNG exists because Medium and other
publishing surfaces do not render Mermaid.

Regenerate after editing a `.mmd`:

```bash
npx @mermaid-js/mermaid-cli -i docs/assets/<name>.mmd -o docs/assets/<name>.png -w 1200 -b white
```

| figure | what it shows |
|---|---|
| `evidence-by-route` | The same 36 reruns read pooled and per route. Pooled bounds the change rate at 9.6%; no single route is bounded better than 39%. |
