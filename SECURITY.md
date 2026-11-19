# Security

gatepack reads local files and runs `ffmpeg`, `ffprobe` and, if installed, EPUBCheck. It makes no
network calls.

If you find a security problem (for example a crafted file that makes a gate execute code or read
files outside its input), please report it privately through
[GitHub security advisories](https://github.com/Essa366/gatepack/security/advisories/new)
instead of a public issue.
