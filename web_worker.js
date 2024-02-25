"use strict";

self.importScripts("https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js");

async function loadPyodideAndFiles() {
  self.pyodide = await loadPyodide();

  async function fetchFile(fileName) {
    const response = await fetch(fileName);
    if (!response.ok) {
      throw new Error(`Could not fetch '${fileName}'. HTTP response status code: ${response.status}`);
    }
    const fileBuffer = await response.arrayBuffer();
    const fileBytes = new Uint8Array(fileBuffer);
    self.pyodide.FS.writeFile(fileName, fileBytes);
  }

  await fetchFile("shadowrun_randomizer.py");
  await fetchFile("initial_item_state.bin");
}
const pyodideReadyPromise = loadPyodideAndFiles();



async function runRandomizer(event) {
  await pyodideReadyPromise;

  const randomizerArgs = event.data;
  const romBytes = randomizerArgs.get("romBytes");
  const seedString = randomizerArgs.get("seedString");
  const itemDuplication = randomizerArgs.get("itemDuplication");
  const spoilerLog = randomizerArgs.get("spoilerLog");

  const romFileName = "shadowrun.sfc";
  pyodide.FS.writeFile(romFileName, romBytes);
  const mockArgv = ["shadowrun_randomizer.py"];
  mockArgv.push("--dry-run");
  if (seedString) {
    mockArgv.push("--seed");
    mockArgv.push(seedString);
  }
  if (itemDuplication) {
    mockArgv.push("--allow-item-duplication");
  }
  if (spoilerLog) {
    mockArgv.push("--spoiler-log");
  }
  mockArgv.push("--");
  mockArgv.push(romFileName);
  pyodide.globals.set("mockArgv", pyodide.toPy(mockArgv));

  const pythonCode = `
import contextlib
import importlib.util
import io
import sys
import unittest.mock
import zipfile

# Dynamically import the randomizer script as a module.
# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
module_name = "shadowrun_randomizer"
file_path = "shadowrun_randomizer.py"
spec = importlib.util.spec_from_file_location(module_name, file_path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
with contextlib.redirect_stdout(io.StringIO()) as stdout:
    # Abuse the unit-test framework to supply the command-line arguments.
    with unittest.mock.patch("sys.argv", mockArgv):
        spec.loader.exec_module(module)
    capturedOutput = stdout.getvalue()

basename, dot, extension = module.outFileName.rpartition(".")
if basename and extension:
    newBasename = basename
else:
    newBasename = module.outFileName

# Create an in-memory zip file containing the randomizer output.
zipBuffer = io.BytesIO()
with zipfile.ZipFile(zipBuffer, "w") as zf:
    zf.writestr(f"{newBasename}.sfc", module.romBytes)
    zf.writestr(f"{newBasename}.txt", capturedOutput)
zipBytes = zipBuffer.getvalue()
zipFileName = f"{newBasename}.zip"
attemptNumber = module.attemptNumber
`
  pyodide.runPython(pythonCode);

  const zipBytes = pyodide.globals.get("zipBytes").toJs();
  const zipFileName = pyodide.globals.get("zipFileName");
  const attemptNumber = pyodide.globals.get("attemptNumber");
  const generatedSeed = new Map();
  generatedSeed.set("zipBytes", zipBytes);
  generatedSeed.set("zipFileName", zipFileName);
  generatedSeed.set("attemptNumber", attemptNumber);
  self.postMessage(generatedSeed, [zipBytes.buffer]);
}
self.addEventListener("message", runRandomizer);
