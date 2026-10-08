import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import en from "@/lib/locales/en.json";

const FRONTEND = join(__dirname, "..");

function sourceFiles(dir: string, found: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (["node_modules", ".next", "coverage", "locales"].includes(name)) continue;
    const path = join(dir, name);
    if (statSync(path).isDirectory()) sourceFiles(path, found);
    else if (/\.(ts|tsx)$/.test(name) && !/\.test\./.test(name)) found.push(path);
  }
  return found;
}

describe("translations bundled with the frontend", () => {
  it("are in sync with /locales (run scripts/sync_frontend_locales.py when this fails)", () => {
    const python = process.env.PYTHON ?? "python";
    expect(() => execFileSync(python, [join(FRONTEND, "..", "scripts", "sync_frontend_locales.py"), "--check"], { stdio: "pipe" })).not.toThrow();
  });

  it("contain every key the code asks for, so no page ever shows a raw key like landing.hero.title_line1", () => {
    const used = new Set<string>();
    for (const file of sourceFiles(FRONTEND)) {
      for (const match of readFileSync(file, "utf-8").matchAll(/\bt\(\s*["']([a-zA-Z0-9_.-]+)["']/g)) used.add(match[1]);
    }
    const missing = [...used].filter((key) => !(key in en)).sort();
    expect(missing).toEqual([]);
  });
});
