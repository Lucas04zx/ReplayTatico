import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const demo = fileURLToPath(new URL("./", import.meta.url));
const root = fileURLToPath(new URL("../", import.meta.url));
const studio = join(root, "replay_tatico");
const target = join(root, "dist-demo");
const template = await readFile(join(studio, "templates/index.html"), "utf8");
const notice = `
    <p class="demo-notice"><strong>Demonstração online.</strong> Dois lances processados localmente, exibidos em um campo esquemático. A importação, a inferência e os replays com vídeo estão na <a href="https://github.com/Lucas04zx/ReplayTatico#instalação">versão local</a>.</p>`;
const html = template
  .replaceAll(/{{\s*url_for\('static', filename='([^']+)'\)\s*}}/g, "./static/$1")
  .replace("<body>", '<body data-demo="true">')
  .replace("  <main>", "  <main>" + notice)
  .replace('<form id="import-form">', '<form id="import-form" hidden>')
  .replace('aria-pressed="true">Original</button>', 'aria-pressed="true">Esquema</button>')
  .replace("</head>", '  <link rel="stylesheet" href="./static/demo.css">\n</head>');

if (html.includes("{{") || !html.includes('data-demo="true"') || !html.includes(">Esquema</button>")) {
  throw Error("O template local mudou e precisa ser revisado para a demonstração.");
}
await mkdir(join(target, "static"), { recursive: true });
await writeFile(join(target, "index.html"), html);
for (const name of ["studio.css", "studio.js", "effects.js"]) {
  await cp(join(studio, "static", name), join(target, "static", name));
}
for (const name of ["demo.js", "demo.css"]) {
  await cp(join(demo, name), join(target, "static", name));
}
await cp(join(demo, "data"), join(target, "data"), { recursive: true });
console.log("Demonstração estática montada em dist-demo.");
