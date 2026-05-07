# Architecture

This document explains what this system does, why it's built the way it is,
and what changes between the public demo in this repo and the production
deployment it was modelled after at TTFA Academy (2023–2024).

## Goals

The original problem was a single AWS region outage taking down a learning
platform that ~1000 students depended on for live classes. The replacement
needed to:

1. Detect a regional failure within a few seconds, not minutes.
2. Shift live traffic to a healthy region with no manual cutover.
3. Survive the loss of an entire cloud, not just a region.
4. Bring the recovered region back online without immediately re-exposing
   it to full traffic — the most common cause of post-recovery incidents
   is a region that *looks* healthy but isn't.
5. Be runnable on a startup budget — no enterprise DR appliances, no
   active-active multi-master databases.

## Topology at a glance

```
                           ┌────────────────────┐
                           │       Users        │
                           └─────────┬──────────┘
                                     │
                                     ▼
                           ┌────────────────────┐
                           │  Cloudflare LB     │
                           │  + health monitor  │
                           └─────────┬──────────┘
                                     │  failover order
                ┌────────────────────┼────────────────────┐
                ▼                    ▼                    ▼
      ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
      │   AWS Mumbai     │ │  AWS Singapore   │ │      Azure       │
      │   (priority 1)   │ │   (priority 2)   │ │   (priority 3)   │
      │   ECS Fargate    │ │   ECS Fargate    │ │  Container Apps  │
      │   ALB + N tasks  │ │  ALB + warm pod  │ │   warm replica   │
      └────────┬─────────┘ └─────────┬────────┘ └─────────┬────────┘
               │                     │                    │
               └─────────────────────┼────────────────────┘
                                     ▼
                           ┌────────────────────┐
                           │   MongoDB Atlas    │
                           │   multi-region     │
                           │   replica set      │
                           └────────────────────┘
```

The key idea: **traffic-tier failover is fast, the data tier is one logical
database**. Atlas owns replication. The application tier is stateless and
identical across all three regions; what changes is which region is in the
hot path.

## Why active-passive over active-active

Active-active would have been more expensive and more dangerous:

- Three regions accepting writes against one logical database means three
  potential sources of write conflicts. With Atlas replica sets, writes go
  to the primary node only. Routing user writes from three regions into a
  single primary turns one region into a write-hot spot anyway, so the
  "active-active" benefit disappears at the data layer.
- Active-active also requires N times the steady-state capacity. For a
  bootstrap budget, paying for three full warm regions all the time was
  not viable. Active-passive lets the standby tiers run at reduced
  replica count (`min_replicas=1` on Azure, `desired_count=1` on AWS
  Singapore) and scale up on takeover.
- Most importantly: active-passive has a *clear* invariant — "users are
  served by exactly one region at a time." Active-active needs distributed
  consensus to maintain consistency, which is operationally heavier and
  far easier to get subtly wrong.

## Failure detection

Cloudflare's health monitor probes `/health/deep` on every pool. The deep
probe checks:

- The application is responding
- Mongo Atlas is reachable from this region
- Critical downstream dependencies (object storage, payment gateway, CDN
  origin) are reachable

`/health/deep` returns 503 if *any* of these fail. The router treats two
consecutive non-200s as "unhealthy" and pulls the pool out of rotation.

Two thresholds matter:

| Threshold | Value | Why |
|-----------|-------|-----|
| `interval` | 30s | Cloudflare LB minimum on the plan we used |
| `unhealthy_threshold` | 2 | Survives one probe loss; flags real outages within 60s |
| `healthy_threshold` | 2 | Prevents flapping when a region briefly recovers |

In the local simulator (this repo) the intervals are tuned much lower
(3s / 15s) so drills run in under a minute.

## Failback: why stepped, not flipped

When AWS Mumbai recovers, the natural urge is to send all traffic back
immediately. This is exactly when post-recovery incidents happen: the
region's load balancer answers, the health endpoint returns 200, but
some internal subsystem (a worker queue, a connection pool that hasn't
fully repopulated, a DNS cache holding stale entries) is still degraded.
Full traffic at that moment causes a second outage and now everyone is
debugging two things.

The canary controller (`router/src/canary.py`) implements a stepped ramp:

```
Step 1:  5% traffic for  120s, target stays HEALTHY → continue
Step 2: 25% traffic for  180s, target stays HEALTHY → continue
Step 3: 50% traffic for  180s, target stays HEALTHY → continue
Step 4: 100% traffic
```

If the target ever transitions away from HEALTHY during a hold window,
weight is set to 0, the controller exits in `rolled_back` state, and
traffic continues to be served from the standby. The hold windows give
real user traffic time to expose problems that synthetic health probes
miss.

In production, the same logic drives the Cloudflare LB API to update
pool weights. In this repo, it drives the in-memory mock router so the
behaviour can be observed end-to-end on a laptop.

## Data layer

Atlas is configured as one cross-region replica set with nodes in
ap-south-1, ap-southeast-1, and centralus. Writes go to the elected
primary; reads from any region default to nearest-secondary with
read concern majority for anything user-facing.

What this gives us:

- A regional failure that takes out the application in Mumbai does not
  take out the database. Atlas re-elects automatically.
- Application config is identical across regions — every pod points at
  the same SRV connection string.
- The application failover and the database failover are **independent**.
  Atlas might re-elect a primary in Singapore even while user traffic is
  still being served by Mumbai. That's fine — Mumbai's app pods just
  start writing to the new primary.

What it doesn't give us:

- Zero-RPO. A write that lands on the old primary microseconds before a
  forced election can be rolled back. For TTFA's workload this was
  acceptable — class enrolment and progress tracking, not money movement.
  For a payments workload, this design needs a different answer.

## Local simulator vs production

| Concern | Production (TTFA) | This repo |
|---------|-------------------|-----------|
| Edge LB | Cloudflare load balancer | FastAPI mock router |
| Compute | AWS ECS Fargate, Azure Container Apps | Docker Compose |
| Database | MongoDB Atlas multi-region | Single Mongo container |
| Health probes | Cloudflare HTTPS monitor | Async httpx loop |
| Canary failback | Cloudflare API + controller | Same controller, in-memory state |
| Failure injection | Iptables rules, region cordon | `/admin/inject-failure` endpoint |

The simulator is faithful where it matters: priority ordering,
threshold-based state transitions, and the failback logic are the same
code path you would run against a real Cloudflare account, just with a
different transport at the edge.

## What I'd change today

- **Probe frequency.** Cloudflare LB on the plan we used capped probe
  interval at 30s. Moving to a custom Lambda-driven probe with 5s
  intervals would have cut MTTD by ~25s.
- **Per-route health.** A region-wide /health/deep is too coarse. A
  route can be broken (a single dependency) without the region being
  unhealthy. The next version would expose `/health/deep?route=courses`
  and let the LB pool route requests by health-per-path.
- **Automated drill cadence.** The drill we ran manually became the DR
  drill stage in the Jenkins pipeline shown here, so every release
  exercises the failover/failback path. In hindsight this should have
  been there from day one.
