# Report Format

Keep reports concise and evidence-based. Always write the final Markdown report to disk when the task requests a report.

## Template

**Generation Info**
- Generated at: `<generated_at>`
- Hostname: `<hostname>`
- User: `<user>`
- Analysis started at: `<started_at>`
- Report completed at: `<completed_at>`
- Total duration: `<duration>`

**Time Range**
`<start_time>` to `<end_time>`

**Query Method**
- Primary tools: `<tool1>`, `<tool2>`
- Notes: `<pagination / DQL / extra discovery / empty result>`

**Overall Conclusion**
- `<most important finding>`

**Classification Results**
- `<category>`: `<count>`, mainly in `<service/resource>`

**Representative Evidence**
- `service=<service>` `resource=<resource>` `trace_id=<trace_id>`: `<short error message>`

**Judgment / Inference**
- `<fact-based inference>`

**Next Steps**
1. `<next step>`
2. `<next step>`

## Writing Rules

- Use absolute times, not only relative phrases.
- Put conclusions before evidence.
- Mark inferences explicitly.
- Do not paste large raw command output.
- Save the completed report as a `.md` file.
