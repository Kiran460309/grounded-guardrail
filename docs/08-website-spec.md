# 08 — Website spec (single Vite app)
Pages: **Home** (20-second pitch, animated guard OFF vs ON), **Live Demo** (chat + live decision cards +
confidence meter + audit table + toggle), **Compare** (Grounded vs LLM-judge side by side with latency
counters), **Results** (table + threshold curve from eval/results.json), **Integrate** (10-line snippet +
pattern README), **About** (limits, layers, links to repo/article/video).
Design: dark dev-tool aesthetic, one accent colour, large readable decision cards (label, confidence bar,
latency ms, policy badge). Accessible contrast. Mobile-friendly. Data from backend SSE; fall back to a
recorded JSON replay if backend is down.
