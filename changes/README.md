# Changelog fragments

One file per pull request: `changes/<PR number>.<type>.md`, one sentence, written
for users. Types: `feature`, `bugfix`, `removal`, `doc`, `misc`.

    echo "uro14 gains a length prefix that catches truncation." > changes/23.feature.md

`towncrier build` folds them into `CHANGELOG.md` at release time and deletes them.
A PR without a fragment fails the changelog check; add the `no-changelog` label
for changes nobody needs to read about.
