---
applyTo: "packages/**"
---
# Reviewing a package submission

Check each of these and comment on any that fail. Skip style nits.

## Package ID
- The file name (without .yml) is the package ID and must equal the `id` in the app's manifest.
- The ID must be reverse-DNS under a domain the submitter owns, or `com.github.<user>.*` /
  `io.github.<user>.*` where `<user>` is the GitHub account publishing the app.
  - Wrong: `com.local.app`, `com.app.player`, `org.webos.tool`, `com.lge.tool`, an upstream
    project's domain on a fork. `org.webosbrew.*` is only for github.com/webosbrew.
  - If the ID must change, say it has to change in the app and its release manifest too,
    not only the file name here.
- The ID needs at least three dot-separated segments; `myapp` and `com.app` are wrong
  (webOS OSE and LuneOS refuse to install apps with shorter IDs).
- Do not ask to rename a package that is already listed on main.

## Content rules
- No piracy, DRM circumvention or unlicensed IPTV. Only legal IPTV services.
- A port of another project must follow that project's licence.
- `pool: main` means the source is publicly available; closed source must be `non-free`.
  Source-available licences (e.g. CC BY-NC) are acceptable in `main`.
- If the PR description ticks "built with a coding agent", check that it also confirms
  testing on a real webOS TV; ask how the generated code was reviewed if nothing says so.

## Groups
- An app that is another client or fork of an app in conf/groups.yml should set
  `group: <slug>` and use that group's category.
- A submission must not add a group or change a group's lead in conf/groups.yml.

## Protected files
- If the PR changes AGENTS.md, .github/instructions/, conf/ or content/schemas/, say so
  explicitly: these change how submissions are reviewed and need a maintainer's attention.

## Not worth commenting on
- Licence-file layout or formatting.
- OpenGL ES 3.1 fallbacks: TVs ship GLES 2.0, 3.0 or 3.2.
