# Changelog fragments

One file per pull request: `changes/<PR number>.<type>.md`, one sentence, written
for users. Types: `breaking`, `feature`, `bugfix`, `removal`, `doc`, `misc`.

    echo "uro14 gains a length prefix that catches truncation" > changes/23.feature.md

Keep it short. towncrier renders the fragment under its type heading and glues the
PR link onto the end, so do not restate the heading ("Added ...", "Fixed ...") and
do not end with a period. State the change and the one fact a reader needs to know
whether it affects them; leave the reasoning to the docs.

Fix what a release actually broke for someone. A bug caught by review on code that
has not shipped yet needs no fragment: use the `no-changelog` label.

Two fragments with byte-identical text render as one entry carrying both PR links.
The benchmark note shared by #37, #39 and #43 relies on this, so the three move
together or not at all.

`towncrier build` folds them into `CHANGELOG.md` at release time and deletes them.
A PR without a fragment fails the changelog check; add the `no-changelog` label
for changes nobody needs to read about.
