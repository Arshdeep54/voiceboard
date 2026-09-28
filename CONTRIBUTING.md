# Contributing

Keep the project local-first and small. Do not add cloud speech recognition,
prompt storage, analytics, accounts, or dependencies without a concrete need.

Before submitting a change:

```sh
python3 -m py_compile voice_receiver/server.py
python3 -m unittest -v test_receiver.py
```

Pull requests run the GitHub Actions test matrix and package build. Releases
are published to PyPI only from a published GitHub Release after PyPI Trusted
Publishing has been configured for this repository.

Changes that affect the phone UI should be tested in Chrome on Android and
should preserve Unicode, multiline text, token rejection, and the Tailscale-only
default.
