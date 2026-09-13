const allowedModes = new Set(["none", "trivial", "disclosed"]);

function disclosureMode(body) {
  const lines = body
    .split(/\r?\n/)
    .filter((line) => /^\s*AI assistance:/i.test(line));

  if (lines.length === 0) return { mode: "none" };
  if (lines.length > 1) {
    return { error: "Keep one AI assistance declaration in the pull request." };
  }

  const mode = lines[0].split(":", 2)[1].trim().toLowerCase();
  if (!allowedModes.has(mode)) {
    return { error: "AI assistance must be none, trivial, or disclosed." };
  }
  return { mode };
}

function commitDisclosure(commit) {
  const assistedLines = commit.message
    .split(/\r?\n/)
    .filter((line) => /^Assisted-by:/i.test(line));
  const scopeLines = commit.message
    .split(/\r?\n/)
    .filter((line) => /^AI(?:-| )Scope:/i.test(line));
  const validAssisted = assistedLines.every((line) =>
    /^Assisted-by:\s*[^:\r\n]+:[^\s\r\n]+\s*$/i.test(line),
  );
  const validScope = scopeLines.every((line) =>
    /^AI-Scope:\s*\S(?:.*\S)?\s*$/i.test(line),
  );
  const disclosed = assistedLines.length > 0 || scopeLines.length > 0;

  return {
    disclosed,
    valid:
      disclosed &&
      assistedLines.length > 0 &&
      scopeLines.length > 0 &&
      validAssisted &&
      validScope,
  };
}

function checkDisclosure(body, commits) {
  const errors = [];
  const declared = disclosureMode(body);
  if (declared.error) errors.push(declared.error);

  let disclosed = 0;
  for (const commit of commits) {
    const result = commitDisclosure(commit);
    if (!result.disclosed) continue;
    disclosed++;
    if (!result.valid) {
      errors.push(
        `${commit.sha.slice(0, 7)} must contain valid Assisted-by and AI-Scope trailers.`,
      );
    }
  }

  if (!declared.error && declared.mode === "disclosed" && disclosed === 0) {
    errors.push(
      "AI assistance is disclosed, but no commit contains the required trailers.",
    );
  }
  if (
    !declared.error &&
    declared.mode !== "disclosed" &&
    disclosed > 0
  ) {
    errors.push(
      "Set AI assistance to disclosed when a commit contains disclosure trailers.",
    );
  }

  return errors;
}

module.exports = { checkDisclosure };
