# Local Web Workbench

Launch SIDScope's isolated local browser workbench on loopback (`127.0.0.1`):

```sh
python3 tools/serve_demo.py --port 8765
```

Open <http://127.0.0.1:8765> in a browser.

## Security & Isolation Guarantees

- Binds to `127.0.0.1` by default and validates `Host` and `Origin` headers.
- Serves HTML with a per-request CSP script nonce and `X-Content-Type-Options: nosniff`.
- Each verification run copies the manifest-tracked portal & evidence files into a fresh temporary directory, checks SHA-256 hashes against `PACKAGE_MANIFEST.json`, runs the pure-Python RQ1–RQ3 + C1 rejection + 8-table rebuild workflow in an isolated subprocess (`python3 -I -B`), and removes the temporary directory automatically.
- Custom CSV audits execute purely in-memory against bounded row limits and never mutate the repository.
