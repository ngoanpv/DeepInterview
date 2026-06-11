# @deepinterview/ee

The **open-core extension seam**. This OSS package ships inert defaults
(`features.*` all `false`, `edition: "oss"`) under Apache-2.0 — the OSS build
behaves identically with or without it.

A downstream distribution (e.g. a hosted/commercial edition) maintains its own
repo and replaces the **contents** of `packages/ee` — same package name, same
exported surface — with real implementations. pnpm workspace resolution then
serves that implementation to every importer. No conditional imports, no build
flags, no edits to OSS files.

Rules for evolving the seam (upstream-first):

1. Hook points are added **here**, in the OSS repo, with inert defaults.
2. OSS code may import this package unconditionally and must behave identically
   with the defaults.
3. Real (non-default) functionality never lands in this stub.
