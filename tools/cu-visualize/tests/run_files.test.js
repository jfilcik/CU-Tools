const assert = require("node:assert/strict");
const test = require("node:test");
const {buildRunIndex, findFile} = require("../run_files.js");

function file(path, data) {
  return {
    name: path.split("/").pop(),
    webkitRelativePath: `selected/${path}`,
    text: async () => typeof data === "string" ? data : JSON.stringify(data),
  };
}

test("native results retain relative identity without inventing success", async () => {
  const files = [
    file("a/doc.pdf.result.json", {contents: []}),
    file("b/doc.pdf.result.json", {result: {contents: [{fields: {}}]}}),
    file("report.json", {files: []}),
  ];
  const run = await buildRunIndex(files);
  assert.equal(run.native, true);
  assert.equal(run.metadata.results.length, 2);
  assert.equal(run.metadata.successful, undefined);
  assert.equal(run.metadata.results[0].status, "available");
  assert.equal(findFile(run.files, "a/doc.pdf.result.json"), files[0]);
  assert.equal(findFile(run.files, "doc.pdf.result.json"), null);
});

test("source matching never chooses between duplicate basenames", async () => {
  const files = [
    file("a/doc.pdf", ""), file("b/doc.pdf", ""),
    file("results/doc.pdf.result.json", {contents: []}),
  ];
  const run = await buildRunIndex(files);
  assert.equal(findFile(run.documents, "results/doc.pdf"), null);
  assert.equal(findFile(run.documents, "b/doc.pdf"), files[1]);
});

test("a root document is not an ambiguous basename fallback", async () => {
  const files = [
    file("doc.pdf", ""), file("nested/doc.pdf", ""),
    file("results/doc.pdf.result.json", {contents: []}),
  ];
  const run = await buildRunIndex(files);
  assert.equal(findFile(run.documents, "results/doc.pdf"), null);
  assert.equal(findFile(run.documents, "doc.pdf"), files[0]);
});

test("legacy metadata and paths remain supported", async () => {
  const files = [
    file("old/metadata.json", {results: [{document: "doc.pdf", result_file: "doc.json"}]}),
    file("old/doc.json", {result: {contents: []}}),
    file("samples/doc.pdf", ""),
  ];
  const run = await buildRunIndex(files);
  assert.equal(run.native, false);
  assert.equal(findFile(run.files, "doc.json", run.base), files[1]);
  assert.equal(findFile(run.documents, "doc.pdf", run.base), files[2]);
});

test("invalid or missing result evidence fails explicitly", async () => {
  for (const data of ["{", {}, {contents: [null]}, {contents: {}}]) {
    await assert.rejects(buildRunIndex([file("bad.result.json", data)]));
  }
  await assert.rejects(buildRunIndex([file("report.json", {files: []})]));
  await assert.rejects(buildRunIndex([file("metadata.json", {})]));
});

test("multiple legacy runs or duplicate selected paths are ambiguous", async () => {
  await assert.rejects(buildRunIndex([
    file("a/metadata.json", {results: []}),
    file("b/metadata.json", {results: []}),
  ]), /Multiple/);
  await assert.rejects(buildRunIndex([
    file("same.result.json", {contents: []}),
    file("same.result.json", {contents: []}),
  ]), /Duplicate/);
});
