# review-pr

Review a GitHub pull request using the project's coding standards and tiered severity framework.

## Usage

```
/review-pr <pr_number>
```

## Example

```
/review-pr 42
```

## Prompt

You are reviewing a pull request. Follow these steps:

1. **Fetch PR details**:
   ```bash
   gh pr view {PR_NUMBER} --json title,body,author,number,url
   gh pr diff {PR_NUMBER}
   ```

2. **Apply the complete review framework** from `.claude/skills/review-pr/SKILL.md`:
   - Use the four-tier priority system (Tier 1: Runtime bugs → Tier 4: Idiomatic usage)
   - Check all review dimensions defined in the skill
   - Follow the review delivery guidelines (inline comments for Tier 1/3, summary for Tier 2/4)
   - Cross-reference with `.claude/skills/coding-standards/SKILL.md` and `CLAUDE.md`

3. **Output** using the structured format defined in `.claude/skills/review-pr/SKILL.md`
