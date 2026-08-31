# Optional QEMU / Emulator Hook

This directory documents an optional emulator path. Emulator evidence is not the
same as physical hardware evidence and must be labeled separately.

If an emulator runner is added, it should write raw logs under:

```text
results/raw/hil/emulator/
```

and validation metadata under:

```text
results/validation/hil_status.json
```
