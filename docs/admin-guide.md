# PRPN Administrator's Guide

This document describes how to set up and run an instance of PRPN.

## Dependencies

PRPN is written in the Python programming language, and uses the Flask Web
framework. The `requirements.txt` file in the repository's root gives the
dependency in a machine-readable format.

## Running

Before the first run, the `data` directory needs to be initialized by invoking
`flask init` in the repository's root. The database is created automatically
as needed.

A development server can be started by invoking the `app.py` file in the
repository's root, or by invoking the Flask CLI via `flask run`. For
production use, it is *strongly recommended* to embed PRPN into a suitable
WSGI server. For development, additional features can be unlocked by supplying
`FLASK_ENV=development` as an environment variable.

### Required additions

PRPN requires an account management service but does not implement it. The
service to use is discovered via the `AUTH_PROVIDER` environment variable,
whose value is formatted as `<module>:<attribute>`. PRPN imports the
`<module>`, takes the `<attribute>` of it, and assumes that it is a suitable
provider instance.

A testing-only implementation is provided in the `testing/auth_test.py` file,
and can be specified via `AUTH_PROVIDER=testing.auth_test:PROVIDER`. It does
not implement any authentication, and is hence **not suitable for production
use**.

## Administrator account

For certain tasks (including application review), an administrator account is
required. After creating the account via the Web UI, its privileges can be
elevated by the `flask set-user-level <account> 3` CLI command (where
`<account>` is the name of the account, and `3` is the *Enhanced User*
privilege level).

## Additional CLI commands

The full set of backend CLI commands can be discovered by running
`flask --help` in the repository's root.
