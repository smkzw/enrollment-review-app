import { rmSync } from "node:fs";

export default function protocolRealTeardown() {
  rmSync("/tmp/enrollment-review-protocol-real-e2e", { recursive: true, force: true });
  rmSync("/tmp/enrollment-review-protocol-real-e2e-input", { recursive: true, force: true });
}
