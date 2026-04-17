---
description: Build mod from overlays and deploy to D2R game directory
argument-hint: ""
---

# D2R Deploy

Build the mod and deploy it to the game directory.

## Mandatory Steps

### 1. Build

```bash
d2r-mod build
```

If the build fails, stop and diagnose.

### 2. Show diff

```bash
d2r-mod diff --summary
```

Show the user what changed before deploying.

### 3. Deploy

Confirm with the user before deploying, then:

```bash
d2r-mod deploy
```

### 4. Remind user

**D2R caches data at startup. Fully exit and relaunch D2R to see mod changes.**
