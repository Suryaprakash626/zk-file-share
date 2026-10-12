# Zero-Knowledge File Share



Share a file through a link, without the server ever being able to read it.



Files are encrypted **in the browser** with AES-256-GCM before upload. The decryption key lives only in the link's `#fragment`, which browsers never send to the server. The server stores random-looking bytes and nothing else.



## How it works



```

Sender's browser                         Server                    Receiver's browser

----------------                         ------                    ------------------

1. generate random AES-256 key

2. encrypt (name + file) -> blob

3. upload blob  ------------------->  stores blob only

4. build link: /f/<id>#<key>

5. send link  ------------------------------------------------->  6. open link

&#x20;                                                                  7. fetch blob by <id>  <---- server

&#x20;                                                                  8. decrypt with <key> (never sent)

```



## Features



- Client-side AES-256-GCM encryption (Web Crypto API), fresh key and IV per file

- File name is encrypted inside the payload, so the server never sees it

- Expiring links (1 hour, 1 day, 7 days) and download limits (including one-time links)

- Tamper detection: any change to the stored data makes decryption fail

- Rate limiting, 25 MB size limit, strict ID validation (no path traversal)

- Automated tests (pytest)



## Run locally



```bash

python -m pip install fastapi "uvicorn[standard]" pytest httpx

python -m pytest

python -m uvicorn main:app --reload

```



Open http://127.0.0.1:8000.



## API



| Method | Path | Description |

|---|---|---|

| `POST` | `/api/files?ttl=3600&max_downloads=1` | Upload encrypted bytes, returns `{id, expires_at}` |

| `GET` | `/api/files/{id}` | Download encrypted bytes; deleted after the last allowed download |

| `DELETE` | `/api/files/{id}` | Delete immediately |



## Security



See [THREAT_MODEL.md](THREAT_MODEL.md) for what the server can and cannot see, the attacks considered, and known limitations.



## Roadmap



- Streaming/chunked encryption for large files

- Optional password on top of the link (Argon2 key derivation)

- Fix: don't consume a one-time link when the key is wrong

- QR code and countdown on the share page

- Deploy behind HTTPS with a strict Content-Security-Policy

