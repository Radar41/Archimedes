# Provenance Snapshots

Use this directory for generated provenance snapshots that capture the current
git state, recent commits, runtime surface, and canonical document checksums.

Generate a snapshot with:

```bash
make provenance
```

Or write to a custom directory:

```bash
./infra/scripts/capture-provenance.sh /tmp/archimedes-provenance
```
