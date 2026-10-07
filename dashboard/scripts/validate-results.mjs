// Validates public/data/results.json before every build: any missing or invalid block throws, so a broken results
// file fails the build instead of reaching the page. Run with bun (it imports the ESM readers directly).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { validateResults } from "../src/lib/dataHelpers.js";

const path = fileURLToPath(new URL("../public/data/results.json", import.meta.url));
validateResults(JSON.parse(readFileSync(path, "utf8")));
console.log("results.json: valid");
