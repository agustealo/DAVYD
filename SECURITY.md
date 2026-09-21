# DAVYD Security

## Credential policy

DAVYD must never commit provider credentials, API keys, access tokens, or local provider secrets to source control.

Provider credentials are resolved in this order:

1. provider-specific environment variable such as `DAVYD_OPENAI_API_KEY`;
2. generic `DAVYD_API_KEY` environment variable;
3. the operating-system credential vault through Python `keyring`.

`settings.json` is local-only and ignored by Git. It stores non-secret preferences only.

## Required action for the previously committed credential

A credential was previously committed in `settings.json`. Treat it as compromised even if the current file is later deleted.

1. Revoke/rotate the credential at the provider immediately.
2. Remove `settings.json` from the tracked repository.
3. Purge the secret from Git history before considering the incident closed.
4. Run a secret scanner over the rewritten history before pushing it.

Do not reuse the exposed credential.
