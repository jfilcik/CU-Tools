/* Local file indexing only: no service calls or result-file rewriting. */
(function (root) {
  function relativePath(file) {
    const path = (file.webkitRelativePath || file.name).replace(/\\/g, "/");
    return file.webkitRelativePath ? path.split("/").slice(1).join("/") : path;
  }

  function indexFiles(files) {
    const index = Object.create(null);
    const byName = new Map();
    for (const file of files) {
      const path = relativePath(file);
      if (index[path]) throw new Error(`Duplicate selected file: ${path}`);
      index[path] = file;
      const name = path.split("/").pop();
      if (!byName.has(name)) byName.set(name, []);
      byName.get(name).push(file);
    }
    for (const [name, matches] of byName) {
      if (matches.length === 1 && !index[name]) index[name] = matches[0];
    }
    return index;
  }

  function findFile(index, reference, base = "") {
    if (typeof reference !== "string" || !reference) return null;
    const path = reference.replace(/\\/g, "/");
    const exact = index[base + path] || index[path];
    if (exact) return exact;
    const name = path.split("/").pop();
    const matches = new Set(Object.values(index).filter(file => file.name === name));
    return matches.size === 1 ? matches.values().next().value : null;
  }

  async function buildRunIndex(fileList) {
    const files = Array.from(fileList);
    const index = indexFiles(files);
    const documents = indexFiles(files.filter(file => /\.(pdf|png|jpe?g|tiff?)$/i.test(file.name)));
    const metadataFiles = files.filter(file => file.name === "metadata.json");
    if (metadataFiles.length > 1) {
      throw new Error("Multiple legacy metadata files found; select one run folder.");
    }
    if (metadataFiles.length === 1) {
      const file = metadataFiles[0];
      const path = relativePath(file);
      const base = path.slice(0, path.lastIndexOf("/") + 1);
      const metadata = JSON.parse(await file.text());
      if (!metadata || !Array.isArray(metadata.results)) {
        throw new Error("Legacy metadata.json must contain a results array.");
      }
      return {files: index, documents, metadata, base, native: false};
    }

    const resultFiles = files.filter(file => /\.result\.json$/i.test(file.name))
      .sort((a, b) => relativePath(a).localeCompare(relativePath(b)));
    if (!resultFiles.length) {
      throw new Error("Select native *.result.json files or a legacy run with metadata.json.");
    }
    const results = [];
    for (const file of resultFiles) {
      let data;
      try {
        data = JSON.parse(await file.text());
      } catch {
        throw new Error(`Invalid result JSON: ${relativePath(file)}`);
      }
      const contents = data && (data.result ? data.result.contents : data.contents);
      if (!Array.isArray(contents) ||
          contents.some(item => !item || typeof item !== "object" || Array.isArray(item))) {
        throw new Error(`Missing or invalid CU contents: ${relativePath(file)}`);
      }
      const path = relativePath(file);
      results.push({
        document: path.replace(/\.result\.json$/i, ""),
        result_file: path,
        status: "available",
      });
    }
    return {
      files: index, documents, base: "", native: true,
      metadata: {results, iterations: 1, analyzer_id: null},
    };
  }

  const api = {buildRunIndex, findFile};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.cuRunFiles = api;
})(globalThis);
