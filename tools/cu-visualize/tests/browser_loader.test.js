const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const cuRunFiles = require("../run_files.js");

function element() {
  return {
    style: {}, children: [], classList: {add() {}, remove() {}, toggle() {}},
    clientWidth: 1000, clientHeight: 800,
    addEventListener() {}, setAttribute() {},
    appendChild(child) { this.children.push(child); return child; },
    removeChild(child) { this.children = this.children.filter(item => item !== child); },
    getBoundingClientRect: () => ({width: 1000, height: 800, left: 0, top: 0}),
    querySelectorAll: () => [],
    getContext: () => ({clearRect() {}, fillRect() {}, fillText() {}, setTransform() {}}),
  };
}

test("actual viewer loads native folders and navigates without legacy metadata", async () => {
  const elements = new Map();
  const alerts = [];
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    createElement: element,
    querySelectorAll: () => [],
    addEventListener() {},
    body: element(),
  };
  const context = vm.createContext({
    document, cuRunFiles,
    window: {addEventListener() {}, innerWidth: 1200},
    localStorage: {getItem: () => null, setItem() {}},
    pdfjsLib: {GlobalWorkerOptions: {}},
    console: {log() {}, warn() {}, error() {}},
    alert: message => alerts.push(message),
    setTimeout: callback => callback(),
  });
  const html = fs.readFileSync(path.join(__dirname, "..", "cuDocVisualizer.html"), "utf8");
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  vm.runInContext(script, context);
  const files = ["a", "b"].map(folder => ({
    name: "doc.pdf.result.json",
    webkitRelativePath: `selected/${folder}/doc.pdf.result.json`,
    text: async () => JSON.stringify({contents: [{fields: {}}]}),
  }));
  context.selectedFiles = files;
  await vm.runInContext("loadTestRun(selectedFiles)", context);
  assert.deepEqual(alerts, []);
  assert.match(document.getElementById("runStats").textContent, /not verified/);
  assert.equal(vm.runInContext("runMetadata.results.length", context), 2);
  await vm.runInContext("navigateToDoc(1)", context);
  assert.deepEqual(alerts, []);
  assert.equal(vm.runInContext("currentDocIndex", context), 1);
  assert.equal(vm.runInContext("pdfDoc", context), null);
});
