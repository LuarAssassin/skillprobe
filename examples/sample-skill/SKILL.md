---
name: sample-code-review
description: >
  A sample skill for code review best practices.
  Use when reviewing code, refactoring, or discussing code quality.
metadata:
  author: skillprobe-team
  version: "1.0.0"
---

# Code Review Best Practices

## When to Use

Trigger this skill when:
- Reviewing pull requests
- Discussing code quality
- Refactoring existing code
- Designing new modules

## Core Principles

1. **Readability over cleverness**: Code should be easy to understand at first glance.
2. **Single responsibility**: Each function/class should do one thing well.
3. **Meaningful names**: Variables and functions should describe their purpose.
4. **Error handling**: Always handle edge cases explicitly.
5. **Test coverage**: Critical paths must have tests.

## Review Checklist

- Does the code follow the project's style guide?
- Are there any obvious bugs or logic errors?
- Is error handling adequate?
- Are there any security concerns?
- Is the code DRY (Don't Repeat Yourself)?
- Are variable names descriptive?
- Is the code well-documented where needed?
- Are there adequate tests?

## Anti-patterns to Flag

- God functions (>50 lines)
- Deep nesting (>3 levels)
- Magic numbers without constants
- Swallowed exceptions
- Commented-out code blocks
- Unused imports or variables
