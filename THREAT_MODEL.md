# Threat Model



## Goal



The server operator, and anyone who breaks into the server or its storage, cannot read shared files or learn their names.



## Design



- The browser generates a random 256-bit AES-GCM key per file and a random 96-bit IV.

- Plaintext = 2-byte name length + file name + file bytes. It is encrypted as one unit.

- Only `IV || ciphertext || auth tag` is uploaded.

- The key is placed in the URL fragment (`#...`). Browsers do not send fragments in HTTP requests or in the `Referer` header.



## What the server can see



| Data | Visible? |

|---|---|

| File contents | No |

| File name | No |

| Encryption key | No |

| File size (plus 28 bytes) | Yes |

| Upload time, expiry, download count | Yes |

| Uploader / downloader IP addresses | Yes (standard in web servers) |



## Attacks considered



| Attack | Result |

|---|---|

| Attacker steals the server's storage | Gets only ciphertext. No keys are stored. |

| Attacker modifies a stored blob | AES-GCM authentication fails, so decryption is refused. |

| Path traversal via the file ID | IDs must match `^[0-9a-f]{32}$`; anything else returns 404. |

| Guessing a file ID | 128 random bits, and the key is still needed to read it. |

| Brute-forcing or flooding uploads | Per-IP rate limit and a 25 MB cap. |

| Race on one-time links | Downloads are serialized with a lock, so only one request wins. |

| Link previews or bots burning a one-time link | The page fetches the file only when the user clicks the button. |

| Expired data lingering on disk | Deleted on access and purged on each upload. |



## Known limitations (honest list)



1. **Web delivery trust.** The server delivers the JavaScript that does the encryption. A malicious or compromised server could ship altered code that leaks keys. This is the core limit of browser-based end-to-end encryption. Mitigations: open source code, a strict CSP, and (future) a CLI or extension that does not rely on server-delivered code.

2. **Link sharing channel.** Anyone who sees the full link can read the file. Send it over a trusted channel. A password option is planned.

3. **Wrong key consumes a one-time link.** The blob is fetched before decryption is attempted.

4. **Metadata leaks** (size, timing, IP) as listed above.

5. **In-memory rate limiter** resets on restart and is per-process only.

6. **Whole file in memory.** Files are encrypted and uploaded in one piece (25 MB cap) rather than streamed.

7. **No HTTPS in local mode.** Production must run behind TLS. Without it, the page itself can be tampered with in transit.

8. **No malware scanning** of uploaded content (the server cannot read it).

