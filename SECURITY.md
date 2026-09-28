# Security policy

The receiver is intended for a trusted Tailscale tailnet. It uses a fresh
one-run bearer token and plain HTTP behind Tailscale Serve or a private
Tailscale interface. It does not provide accounts, TLS itself, or internet
exposure.

Do not use `--host 0.0.0.0` on an untrusted network. Do not enable router port
forwarding or Tailscale Funnel for this service.

If you discover a security issue, please open a private report with the
maintainer rather than publishing a working exploit first.
