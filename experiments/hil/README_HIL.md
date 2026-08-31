# LedgerGuard Hardware-in-the-Loop Hooks

The HIL framework is intentionally opt-in. The strong evaluation pipeline must
not claim hardware validation unless real hardware logs are produced.

## Supported Hook Types

- `device_agent_linux/`: Python agent for a Linux SBC such as a Raspberry Pi.
- `device_agent_mcu/`: MCU/MCUboot integration placeholder.
- `qemu_or_emulator_optional/`: optional emulator notes and status hook.

## Required Environment

Set `LEDGERGUARD_HIL_DEVICE_CONFIG` to a JSON file describing the real device.

Example:

```json
{
  "device_id": "pi4-lab-01",
  "device_type": "linux_sbc",
  "os": "Debian 12",
  "bootloader": "U-Boot",
  "agent": "device_agent_linux"
}
```

If the variable is not set, the runner writes:

```json
{
  "status": "not_run",
  "reason": "LEDGERGUARD_HIL_DEVICE_CONFIG is not set"
}
```

## Required Evidence for Claiming HIL Results

For a HIL row to be included in main results, raw logs must include:

- device ID or pseudonym
- device type
- OS/firmware version
- bootloader or update framework version
- release ID
- target version
- outcome
- timestamp
- receipt hash
- raw command log

Without those files, HIL must remain `not_run` and must not appear as measured
hardware evidence in manuscript tables.
