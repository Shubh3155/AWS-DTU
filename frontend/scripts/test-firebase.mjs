import { spawnSync } from "node:child_process";

function run(command, argumentsList, options = {}) {
  const result = spawnSync(command, argumentsList, { stdio: "inherit", ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
run(process.execPath, ["--test", "firebase-tests/firestore.test.mjs"]);
run("npx", ["playwright", "test", "--config", "playwright.firebase.config.ts"]);
run("./.venv/bin/python", ["-m", "pytest", "-q", "tests/test_firebase_emulator.py"], { cwd: "../backend" });
