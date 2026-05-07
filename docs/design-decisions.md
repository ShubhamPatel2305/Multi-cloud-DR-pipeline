# Design decisions

A handful of choices that shaped this system. Each entry is the
context, the options that were on the table, and what was picked.

## D1. Cloudflare LB vs Route 53 + AWS Global Accelerator

**Context.** Need an L7 traffic steering layer in front of three regions
across two clouds.

**Options.**

- **Route 53 with health-checked failover.** Free, AWS-native, but DNS-based.
  TTL games, no real L7 awareness, and the cross-cloud story (AWS health
  checks against Azure endpoints) is awkward.
- **AWS Global Accelerator.** Anycast IP, fast failover, but AWS-only on
  the origin side — Azure pools require workarounds.
- **Cloudflare LB.** Already used for DNS and CDN. Single dashboard for
  multi-cloud pools. HTTPS health probes, not just TCP. Fast failover
  without DNS TTL games (proxied hostname, no DNS hop on cutover).

**Picked.** Cloudflare. The "no DNS hop on cutover" property is what
unlocks the sub-minute RTO target. With Route 53 we'd be at the mercy of
client and resolver TTLs.

## D2. Active-passive vs active-active

Discussed in `architecture.md`. Short version: active-active was the wrong
shape for this workload (single logical primary, write-conflict surface)
and the wrong shape for the budget.

## D3. Canary failback as a custom controller, not a Cloudflare feature

**Context.** Cloudflare LB pools can be weighted, but pool ordering is
ordinal — there's no first-class "ramp this pool from 0 to 100% over T
minutes if these health probes stay green" feature.

**Options.**

- **Two pools, swap origins.** Run a "canary primary" pool with weight
  ramped up. Operationally messy, doubles the number of pool definitions.
- **Lambda-driven controller.** Sit a Lambda on a 5s schedule, read
  health, drive Cloudflare API calls. The shape we picked.
- **Manual ramp via dashboard.** Doesn't scale, doesn't survive on-call
  rotation.

**Picked.** Custom controller. Implemented in this repo as
`router/src/canary.py`. In production it ran as a small service alongside
the deployment pipeline and called the Cloudflare LB API.

The interesting design property is that the controller's only state is
the current run (target + step + start time). All the *decisions* are
re-derived from the LB monitor's view. If the controller pod restarts
mid-run, it doesn't try to "resume" — it lets the next operator decide
whether to start a fresh canary against the same target.

## D4. MongoDB Atlas vs running our own replica set

**Context.** Need a database that survives a regional failure and ideally
replicates cross-cloud.

**Options.**

- **Self-hosted Mongo replica set across regions.** Full control, more
  ops burden. Also requires VPC peering between AWS and Azure, which is
  a private-link config nightmare.
- **DocumentDB / Cosmos DB.** Either ties us to one cloud.
- **Atlas multi-region replica set.** Managed, spans clouds, has a
  reasonable Free / M-series cost curve.

**Picked.** Atlas. The cross-cloud-replication-as-a-service value is
worth a lot relative to the cost. The escape hatch (point a Mongo URI at
a self-hosted cluster) is preserved by isolating connection-string
config in `MONGO_URI`.

## D5. ECS Fargate vs EKS for the AWS regions

**Context.** Need stateless container workload across two AWS regions.

**Picked.** Fargate. EKS would have given us more control but with much
higher operational surface area for a startup-sized team. The application
is stateless, so we don't need StatefulSet semantics; service mesh for
intra-region service discovery wasn't justified at the size.

## D6. Azure Container Apps vs App Service

**Context.** Cross-cloud DR target. Wanted something that:

- Boots a container fast on takeover (< 60s)
- Doesn't bill for steady-state idle (or bills small)
- Has L7 ingress with HTTPS termination

**Picked.** Container Apps with `min_replicas=1`. App Service plan would
have billed for the entire VM whether traffic was flowing or not.
Container Apps charges per-vCPU-second on active replicas, with a small
floor for the warm replica. The warm replica is the deliberate cost we
pay to keep takeover RTO under our 90s target.

## D7. Failure injection through the application, not the network

**Context.** Need to drill the failover/failback path regularly.

**Options.**

- **iptables drop.** Authentic, but requires shell access and root in
  the container — and it doesn't easily let us pick *which* dependency
  is broken.
- **Stop the container.** Too coarse — exercises the failover path, but
  not the "lying health check" scenario which is where most of the
  interesting bugs are.
- **`/admin/inject-failure` endpoint.** Lets us flip a specific health
  endpoint to 503 while leaving others green. Simulates partial
  failures, which match real production failures more often than total
  outages do.

**Picked.** The endpoint, with the constraint that it's hard-disabled in
`APP_ENV=prod`. Production drills are run against a parallel staging
environment that has the endpoint enabled.

## D8. Why simulate, not just document

This repo is a public artifact, so it has to be runnable. Anyone
reviewing the code can `make up`, watch failover happen on their own
laptop, and trust that the design they're reading is the design that
runs. That's a much higher bar than a slide deck — and it forced honest
choices everywhere (no hand-waving "Cloudflare just handles it"; the
mock router exists because the actual logic has to live somewhere).
