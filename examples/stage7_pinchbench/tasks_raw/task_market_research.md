---
id: task_market_research
name: Competitive Market Research
category: research
grading_type: hybrid
timeout_seconds: 300
workspace_files: []
---
## Prompt
Create a competitive landscape analysis for the **enterprise observability and APM (Application Performance Monitoring)** market segment. Based on your knowledge, identify the top 5 players, their key differentiators, market trends, and typical pricing models.
**IMPORTANT: You MUST save your report to a file named exactly `market_research.md` in the current working directory.** Do not just output the report in your response — the file must be written to disk. The filename must be exact (not `market-research.md`, not in a subdirectory).
Structure your report with sections for each competitor and a summary comparison table.
If you have access to web search tools, use them to gather the most current information. Otherwise, use your knowledge of this market to produce a thorough analysis.
## Expected Behavior
The agent should:
1. Identify the major competitors (e.g., Datadog, New Relic, Dynatrace, Splunk, Grafana Labs, Elastic, etc.)
2. For each competitor, document:
   - Company overview and market position
   - Key product differentiators
   - Typical pricing model (per-host, per-GB, per-user, etc.)
   - Notable strengths and weaknesses
3. Identify overall market trends (AI/ML integration, OpenTelemetry adoption, consolidation, cloud-native, etc.)
4. Create a well-organized Markdown report with:
   - An executive summary
   - Individual competitor profiles
   - A comparison table
   - Market trends section
## Grading Criteria
- [ ] File `market_research.md` created
- [ ] Report identifies at least 5 competitors
- [ ] Each competitor has a meaningful profile (not just a name)
- [ ] Report includes a comparison table or matrix
- [ ] Report covers pricing models for competitors
- [ ] Report discusses current market trends
- [ ] Information appears current and sourced from the web (not purely generic)
- [ ] Report has clear structure with headings and sections
- [ ] Executive summary or introduction is present
- [ ] Writing quality is professional and analytical
