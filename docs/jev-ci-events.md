# Event-driven Jev CI events

The FRDM i.MX95 workflow emits one signed event when the image-build outcome
is known. It does not run a watcher or ask a model to check CI status.

On failure, the runner keeps the raw build log local, extracts the bounded and
redacted failure envelope, and sends only that envelope to the central
gateway. The gateway makes one read-only `jev_ci_triage` call through Preloop.
The resulting JSON and Markdown are non-required advisory artifacts; they
cannot retry CI, change status, authorize work, or mark a build green.

On success, the runner sends no log and makes no Jev call. It emits only the
GitHub run identity, commit SHA, run URL, and the private runner evidence path.
The gateway records the idempotent event with the action
`resume_waiting_test_lane`, ready for an exact subscribed test-lane consumer.

`JEV_CI_ADVISORY_HMAC_SECRET` authenticates both exact request bodies. The
Preloop credential remains on the gateway host and is never a GitHub secret.
FRDM vendor images and raw logs remain on the self-hosted runner.
