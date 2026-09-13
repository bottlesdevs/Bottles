const test = require("node:test");
const assert = require("node:assert/strict");
const { checkDisclosure } = require("./check-ai-disclosure.cjs");

const plainCommit = { sha: "1111111", message: "fix: repair launch" };
const assistedCommit = {
  sha: "2222222",
  message:
    "docs: explain launch\n\nAssisted-by: Codex:gpt-5\nAI-Scope: Drafted the documentation from the issue description.",
};

test("accepts work without AI assistance", () => {
  assert.deepEqual(checkDisclosure("", [plainCommit]), []);
  assert.deepEqual(
    checkDisclosure("AI assistance: none", [plainCommit]),
    [],
  );
});

test("accepts exempt trivial completions", () => {
  assert.deepEqual(
    checkDisclosure("AI assistance: trivial", [plainCommit]),
    [],
  );
});

test("accepts a disclosed assisted commit", () => {
  assert.deepEqual(
    checkDisclosure("AI assistance: disclosed", [plainCommit, assistedCommit]),
    [],
  );
});

test("requires trailers for disclosed assistance", () => {
  assert.match(
    checkDisclosure("AI assistance: disclosed", [plainCommit])[0],
    /no commit contains/,
  );
});

test("requires the pull request to match its trailers", () => {
  assert.match(
    checkDisclosure("AI assistance: none", [assistedCommit])[0],
    /Set AI assistance to disclosed/,
  );
});

test("rejects incomplete and legacy trailers", () => {
  const commit = {
    sha: "3333333",
    message: "docs: update\n\nAssisted-by: Codex:gpt-5\nAI scope: docs",
  };
  assert.match(
    checkDisclosure("AI assistance: disclosed", [commit])[0],
    /must contain valid/,
  );
});

test("rejects invalid or repeated declarations", () => {
  assert.match(
    checkDisclosure("AI assistance: sometimes", [plainCommit])[0],
    /must be none, trivial, or disclosed/,
  );
  assert.match(
    checkDisclosure(
      "AI assistance: none\nAI assistance: disclosed",
      [plainCommit],
    )[0],
    /Keep one/,
  );
});
