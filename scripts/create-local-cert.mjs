import { chmod, mkdir, rm, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const execFileAsync = promisify(execFile);
const projectRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const certRoot = resolve(projectRoot, "certs");
const caKey = resolve(certRoot, "localhost-ca-key.pem");
const caCert = resolve(certRoot, "localhost-ca.pem");
const serverKey = resolve(certRoot, "localhost-key.pem");
const serverCsr = resolve(certRoot, "localhost.csr");
const serverCert = resolve(certRoot, "localhost.pem");
const extensions = resolve(certRoot, "localhost.ext");

await mkdir(certRoot, { recursive: true });
await writeFile(extensions, [
  "basicConstraints=critical,CA:FALSE",
  "keyUsage=critical,digitalSignature,keyEncipherment",
  "extendedKeyUsage=serverAuth",
  "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1",
].join("\n"));

try {
  await execFileAsync("openssl", [
    "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes",
    "-keyout", caKey, "-out", caCert, "-days", "3650",
    "-subj", "/CN=Twitch Games Local Development CA",
    "-addext", "basicConstraints=critical,CA:TRUE",
    "-addext", "keyUsage=critical,keyCertSign,cRLSign",
  ]);
  await execFileAsync("openssl", [
    "req", "-new", "-newkey", "rsa:2048", "-sha256", "-nodes",
    "-keyout", serverKey, "-out", serverCsr, "-subj", "/CN=localhost",
  ]);
  await execFileAsync("openssl", [
    "x509", "-req", "-in", serverCsr, "-CA", caCert, "-CAkey", caKey,
    "-CAcreateserial", "-out", serverCert, "-days", "825", "-sha256",
    "-extfile", extensions,
  ]);
} catch (error) {
  console.error(error.stderr || error.message);
  process.exitCode = 1;
} finally {
  await Promise.all([
    rm(serverCsr, { force: true }),
    rm(extensions, { force: true }),
  ]);
}

if (process.exitCode !== 1) {
  await Promise.all([chmod(caKey, 0o600), chmod(serverKey, 0o600)]);
  console.log("Created localhost HTTPS certificates in certs/ (ignored by git).");
  console.log("Import certs/localhost-ca.pem into the macOS login keychain and set it to Always Trust.");
  console.log("Then run npm run dev and use https://localhost:4174/ in Twitch Local Test.");
}
