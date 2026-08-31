# MCU / MCUboot Hook

This directory is a placeholder for a real MCU integration. It does not contain
measured MCU results.

Expected future integration points:

- Zephyr or MCUboot update client
- hardware anti-rollback counter readback
- signed receipt export over serial, UART, USB, or debug transport
- bad hash, downgrade, kill switch, and rollback/fail test cases

Until a real integration exists, the HIL runner must mark MCU evidence as
`not_run`.
