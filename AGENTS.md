# Repository instructions

## Generative AI disclosure

Read this section before changing files, creating a commit, or opening a pull
request.

When generative AI contributes more than a trivial completion, add both of
these trailers to every assisted commit:

```plain
Assisted-by: <tool>:<model-version>
AI-Scope: <what the tool generated and the prompt or a short prompt summary>
```

Single-line completions, renames, and formatting changes do not need trailers.
Work completed without generative AI does not need trailers.

Before opening a pull request, set `AI assistance` in the pull request template
to `none`, `trivial`, or `disclosed`. Use `disclosed` when at least one commit
has the trailers above. Review every assisted change before submission.

Do not create the commit or pull request until its disclosure matches the work.
