# Lab 1 skills — install these before you start

Five project skills for the NIST SP 800-63-4 Figure 3 lab. Both partners install all five: they are what keeps two people building against the same contract when they are working in different files at different hours.

| Skill | Fires when | Stage in `PROJECT_WORKFLOW.md` |
|---|---|---|
| `lab1-contract` | Writing or debugging any of the four services, transcripts, `run_id`, timestamps, role transitions | §12 stages 1–4 (inspect → implement) |
| `lab1-conformance` | The probe, any check ID, "unreachable from campus", "why not 24/24" | §12 stage 5 (test) |
| `nist-63-cite` | Any claim about what NIST requires, allows, or prohibits | §12 stage 6 (validate vs spec) |
| `lab1-review` | Security self-review, and the pre-zip hygiene scan | §12 stage 7 (security review) |
| `lab1-adversary` | Red-teaming, denial tests, the adversarial hour, the chosen topic | §8.4 and the written analysis |

They carry three scripts, all POSIX `sh`, no dependencies beyond `curl` and `python3`:

```bash
sh .claude/skills/lab1-conformance/scripts/smoke.sh team.json --full
```

```bash
sh .claude/skills/lab1-review/scripts/hygiene_scan.sh .
```

```bash
sh .claude/skills/lab1-adversary/scripts/attack_curls.sh team.json
```

## Install

**Route 1 — the repository (recommended for the team).** These skills already live in `.claude/skills/` here. Clone the repo and both partners have them, in the same version, automatically. When one of you edits a skill, the other gets the change on the next pull. Nothing else to do.

**Route 2 — personal, available in every project.** Copy the folders into your own skills directory:

```bash
cp -r .claude/skills/lab1-* .claude/skills/nist-63-cite ~/.claude/skills/
```

On Windows that directory is `%USERPROFILE%\.claude\skills\`. Use this route if you also work on the lab outside the repo — reading the NIST PDFs, drafting the analysis, building the deck.

**Route 3 — the packaged `.skill` files.** `dist/skills/*.skill` are self-contained zips, one per skill. Send them to your partner over whatever channel you like. To install, either use the **Save skill** button on the file card if your client shows one, or unzip into the skills directory:

```bash
unzip dist/skills/lab1-contract.skill -d ~/.claude/skills/
```

Rebuild the packages after editing a skill; the `.skill` file is a snapshot, not a link.

## Check it worked

Ask for something the skill covers and see whether it loads — for example *"add the transcript endpoint to the CSP"* should pull in `lab1-contract`, and *"does NIST require password rotation?"* should pull in `nist-63-cite`. If nothing triggers, confirm the folder name matches the `name:` in its `SKILL.md` and that the file starts with the `---` frontmatter block.

## Built-in skills to pair with these

`/init` on day 0 · `anthropic-skills:pdf` for quoting the NIST documents · `/run` to launch the services · `/security-review` and `/code-review` at stage 7 · `/simplify` at stage 8 · `anthropic-skills:docx` and `anthropic-skills:pptx` for the deliverables. See §14 of `PROJECT_WORKFLOW.md`.

## Editing them

Each skill is one `SKILL.md` with YAML frontmatter (`name`, `description`) and Markdown instructions. The `description` is the whole triggering mechanism — if a skill is not firing when it should, that field is what to fix, not the body. Keep the contract in `lab1-contract` in sync with §5 of `PROJECT_WORKFLOW.md`: if the contract changes, it changes in the workflow first, then in the skill, then in code.
