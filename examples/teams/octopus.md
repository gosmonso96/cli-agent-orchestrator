---
name: octopus
display_name: Octopus Analytics
home: ~/OctopusContactAnalytics
agents:
  - code_supervisor
  - developer
steering:
  - ~/.kiro/steering/domains/octopus.md
provider: kiro_cli
env:
  OCTOPUS_ENV: beta
---

Contact analytics for Amazon Freight support. Ingests Contact Lens data,
enriches with order/VRID context, classifies threads via LLM, and surfaces
insights through dashboards.

Key packages: OctopusContactAnalytics, TrailblazerAIApi (octopus lambdas),
TrailblazerAI (octopus pages).
