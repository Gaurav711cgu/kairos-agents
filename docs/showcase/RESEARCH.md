# Research informing the presentation and live workflow

Reviewed 14 October 2026. This is a focused review of primary engineering and interaction sources, followed by changes grounded in Kairos code and receipts. It does not establish an improvement in model repair rates.

## Findings applied

Microsoft’s Human-AI Interaction guidelines call for clear capabilities, context-relevant information, understandable actions and ways to correct failures. The website therefore labels the current experience **Evidence viewer**, keeps **Workbench** as a consistent destination, and explains how to submit a new investigation on the setup page. The homepage introduces the task and earned development demonstration before presenting the full validation comparison. Outcome labels and original evidence remain unchanged. [Microsoft Research guidelines](https://www.microsoft.com/en-us/research/?p=564561), [HAX Toolkit](https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/).

Anthropic recommends simple composable agent workflows, explicit stopping conditions and evaluation suited to the task. Kairos retains its bounded worker rather than adding another orchestration framework. Live reviewer setup connects the existing authenticated API, pinned local inference and worker; resource ownership and a session deadline control shutdown. [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

Anthropic’s evaluation guidance distinguishes the captured transcript from the actual outcome and discusses deterministic graders for coding work. Kairos shows model actions, proposed code, regression checks and existing-test results separately. A new interactive demonstration remains separate from the locked evaluation and never replaces a failed historical attempt. [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

The SWE-agent research studies how the editing and navigation interface affects coding agents. This supports inspecting tool-format failures rather than attributing every error to a model. Kairos’s frozen v7 already records captured-source line handles, invalid edit reasons and immediate check feedback. This delivery does not claim that those mechanics solved its fresh repair study. [SWE-agent paper](https://arxiv.org/abs/2405.15793), [official execution guide](https://swe-agent.com/latest/usage/hello_world/).

## Delivery decisions

- Keep precise deployment information at the point where the visitor chooses inspection or execution.
- Explain the visible action and result before implementation prerequisites.
- Present earned capacity as the headline; retain the earlier failed run in the same report.
- Preserve original captures, checks, study totals and measurement limits.
- Use existing local weights and explicit execution setup. No paid research API or new model experiment is required.

These are implementation judgments informed by the sources, not performance guarantees from the sources. Acceptance uses browser behavior and actual execution receipts.
