# Notes for agents

Guidance for AI agents writing or reviewing package submissions in this repository. The rules for
submitters are in [README.md](README.md); this file adds what a reviewer should check.

GitHub Copilot code review reads this file, and also the shorter checklist in
[.github/instructions/packages.instructions.md](.github/instructions/packages.instructions.md), which it
applies to changes under `packages/`. Keep the two in step when a rule changes.

## Package ID

A package's ID (the `id` in its `appinfo.json`, and the name of its file in `packages/`) must be
reverse-DNS under a domain the developer owns. `com.example.myapp` is only acceptable from whoever
owns `example.com`.

A developer who does not own a domain uses their own GitHub namespace instead:
`com.github.<username>.<app>` or `io.github.<username>.<app>`, where `<username>` is the GitHub
account that publishes the app.

Treat these as wrong:

* A generic or made-up prefix, such as `com.local.*`, `com.custom.*` or `com.app.*`.
* A namespace that looks official, such as `org.webos.*`, `com.webos.*` or `com.lge.*`.
  `org.webosbrew.*` is reserved for packages from github.com/webosbrew.
* Another person's, company's or project's name, such as an upstream project's domain used for a
  fork, or a brand the developer does not own.
* A `github.<username>` segment that does not match the account publishing the app.

The ID is what a TV matches an installed app against, so it has to change in the app itself and its
manifest, not only in the file name here. Packages already listed keep the ID they shipped with:
renaming one would orphan every TV that has it installed.

## Groups

Several apps are clients or forks of the same thing, such as the Jellyfin clients. A package joins
such a group with `group: <slug>`, and the site shows the group as one tile that unfolds to its
members. The groups and their leads are listed in [conf/groups.yml](conf/groups.yml).

* A new package that is another client or fork of an app already in a group should set `group` to
  that group. Ask for it in review if it is missing.
* A submission does not choose the lead, and does not add a group to `conf/groups.yml` for its own
  app. Both are the maintainers' call.
