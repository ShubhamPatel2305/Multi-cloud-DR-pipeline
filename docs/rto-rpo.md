# RTO and RPO

## Targets

| Tier | RTO target | RPO target | How we get there |
|------|-----------|-----------|------------------|
| Application | 60 s | n/a | Cloudflare LB pool failover, threshold = 2 misses |
| Database | 10 s | < 5 s | Atlas replica-set automatic primary election |
| Whole region | 90 s | < 5 s | App + DB failover composed |
| Whole cloud (AWS → Azure) | 180 s | < 5 s | Two-step pool failover, Azure cold-warm |

RTO is wall-clock from "first user-visible 5xx" to "next request served by a
healthy region". RPO is data lost on a forced election in the worst case.

## What dominates each target

### App-tier RTO (~60s)

```
detection (probe interval × threshold)   ~60s
+ pool reshuffle in Cloudflare              ~1s
+ DNS TTL on the LB hostname                 0s   (Cloudflare proxied = no DNS hop)
─────────────────────────────────────────
total                                     ~61s
```

The dominant cost is detection. Halving `interval` halves the RTO until you
hit Cloudflare's plan minimum.

### DB-tier RTO (~10s)

Atlas's election timeout defaults to 10s of `electionTimeoutMillis`. During
that window writes against the old primary fail. Application code retries
writes for up to 8s on `MongoNotPrimaryError`, so most user-visible writes
succeed on the second attempt.

### RPO (< 5s)

Atlas uses majority write concern. A write acknowledged to the client has
been replicated to a majority of voting nodes. The window where a write
*can* be rolled back is the time between write apply on the primary and
replication to a secondary — typically tens of milliseconds, capped at the
oplog flush interval. The 5s number is the worst-case assumption used for
incident playbooks.

## Cross-cloud RTO (~180s)

When the failover crosses clouds (Mumbai + Singapore both unreachable, traffic
must move to Azure), additional cost comes from:

- Azure Container Apps min_replicas=1 means there is one warm pod. At
  takeover, scale-out to handle full load takes ~30–60s.
- Azure's pull of the latest image from the registry on scale-out
  is not amortised. We mitigate by pinning `:latest` to the image already
  on the warm pod (no pull needed for the existing replica).

## Validation

The DR drill in `jenkins/Jenkinsfile` runs on every release:

1. Capture wall-clock t0
2. Inject `deep` failure on Mumbai
3. Poll the router pool until Mumbai is `unhealthy` and Singapore is
   selected — record `t_failover`
4. Run a smoke request against the public hostname, assert 200 — record
   `t_first_healthy_request`
5. Clear the failure, start canary, wait for `completed` — record
   `t_full_recovery`

These four timestamps are emitted as build metadata so the team can
track RTO drift across releases.
