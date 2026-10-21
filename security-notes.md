# Security and Hardning Notes

Scope: FastAPI + Firebase (Auth + Firestore) + Discogs API backend

### Rate Limiting
`slowapi` was put on but turns out, it didn't quite work.

Firstly, Client IP behind Cloud Run would make it so all users share the rate limit. More importantly, `X-Forwarded-For` is spoofable and lets a client send a fake header.

Discogs has its own rate limit of 60 requests per minute shared across the entire app.

Added a per-user limit based on the firebase uid. This would remove the need for the app-wide per-IP limit. Added the 10/minute requests to the Discogs-backed routes and 30/minute on some of the heavy read ones.

Also, turns out the app-wide limit was broken anyway due to new incompatibility between `slowapi` and the latest FastAPI. Something about `slowapi` not being able to scan `app.routes` to get each route. So until that's fixed, the individual decorators are good enough.

### Image Fetch

There were a few missing/bad practices. `urllib.request` will fetch any URL, like file, ftp or http and follow redirect. This opens it to SSRF risks. There's also no size cap on the response, or decompression size checks. CPU costs can also be high for a full-sized image check.

Solutions:
- Allow only https://i.discogs.com
- use httpx.stream() with a 5 MB cap on the data. httpx also doesn't follow redirects
- Check image width and height on image open, and then turn image to thumbnail before sampling
- Use BytesIO instead of the temp file

### Issues found

#### Event-loop blocking
- Lots of endpoints blocked the event loop via async-await, and don't need to, including urllib, PIL, and sync Firestore, freezing every other request on the worker.

#### Memory DoS in `n_sides`:
- Update vinyl endpoint accepts a numerical value for `n_sides`
- Later when a vinyl is "played", the number is turned into an array
- A massive number could exhaust memory

**Fix**: Add a limit to the int in the pydantic model

#### No input validation
- No length limits on strings or arrays
- Firestore docs are capped at 1 MiB. Big strings could cause failures

**Fix**: add string max lengths, hex regex and sides array max

#### Discogs URL injections

- Search term passed in by a user was directly passed to discogs url raw
- Discogs Release and Album endpoints accept path param strings
- Someone could pass something like `../releases` or `../database/search?q=x` and get access to other routes

**Fix**: Always use the HTTP client's `params`

## Important Lessons

- Input validation and bounds: lengths, ranges, sizes, formats
- Never build URLs from raw user input directly
- Server-side fetches need allowlists, size caps, redirect protection, resource limits
- Rate limit by user ID when possible. Be aware of what the "client IP" could be for deployed apps
