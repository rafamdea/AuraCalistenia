const { spawn } = require("node:child_process");
const path = require("node:path");

const python = process.env.HOSTINGER_PYTHON_BIN || "python3";
const pythonPackages = path.join(__dirname, ".python_packages");
const env = {
  ...process.env,
  PYTHONUNBUFFERED: "1",
  PYTHONPATH: [pythonPackages, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
  PORT: process.env.PORT || "8000"
};

const child = spawn(python, ["app.py"], {
  cwd: __dirname,
  env,
  stdio: "inherit"
});

child.on("error", (error) => {
  console.error(`Unable to start AuraCalistenia with ${python}:`, error);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) console.error(`AuraCalistenia stopped by signal ${signal}`);
  process.exit(code ?? 1);
});

for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => child.kill(signal));
}
