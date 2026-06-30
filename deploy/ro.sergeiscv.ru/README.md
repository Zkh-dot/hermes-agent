# ro.sergeiscv.ru deployment state

This directory tracks the non-secret live Hermes state that should survive
cleanups of the `ro.sergeiscv.ru` installation.

- `hermes/profiles/letovo/cron/jobs.json` mirrors
  `/home/yara/.hermes/profiles/letovo/cron/jobs.json`.

Webhook scripts and subscription files are intentionally kept on the host.
Secrets, `.env` files, logs, state databases, and caches are not tracked here.
