# Deployment (AWS EC2 + Docker Compose + Caddy)

Target: one `t3.small` EC2 instance running `docker-compose.prod.yml`. Caddy terminates TLS
with Let's Encrypt. GitHub Actions builds images, pushes them to GHCR and rolls out over SSH
after CI passes on `main`.

> Status: the pipeline and files are ready. Creating the AWS resources and the first deploy
> are manual one-time steps for the project owner (below). Record the public URL in the
> README once it is live.

## One-time setup

1. **DNS:** point `evalops.<your-domain>` (A record) at an Elastic IP.
2. **EC2:** Ubuntu 24.04, t3.small, 20 GB gp3. Security group inbound: 22 (your IP only),
   80, 443. Attach the Elastic IP.
3. **Install Docker** on the instance:

   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker ubuntu && newgrp docker
   sudo mkdir -p /opt/evalops/deploy && sudo chown -R ubuntu /opt/evalops
   ```

4. **Server secrets**: `/opt/evalops/.env`, `chmod 600`:

   ```bash
   ENVIRONMENT=prod
   DOMAIN=evalops.example.com
   IMAGE_OWNER=<github-user-lowercase>
   POSTGRES_PASSWORD=<random>
   JWT_SECRET=<python -c "import secrets;print(secrets.token_urlsafe(48))">
   LLM_PROVIDER=fake            # public demo; set anthropic + ANTHROPIC_API_KEY for real runs
   MAX_COST_PER_RUN_USD=0.50
   MAX_DAILY_COST_USD=5.0        # per project per UTC day
   RATE_LIMIT_PER_MINUTE=60
   DEMO_PASSWORD=<public demo password>
   ```

5. **GHCR access**: make the two packages public after the first push, or `docker login ghcr.io` on the server with a read-only token.
6. **GitHub settings**: environment `production` with secrets `EC2_HOST`, `EC2_USER`
   (`ubuntu`), `EC2_SSH_KEY` (a deploy key added to `~/.ssh/authorized_keys`), and repository
   variables `DOMAIN` and `DEPLOY_ENABLED=true`.

## Every deploy (automatic)

Merge to `main` → `CI` green → `Deploy` workflow:
build both images (tag = short SHA) → push to GHCR → Trivy scans the backend image
(fails on CRITICAL) → copy compose + Caddyfile → `docker compose pull && up -d --wait`
(the one-shot `migrate` service runs `alembic upgrade head` before `api`/`worker` start) →
`curl https://$DOMAIN/healthz` must succeed.

Seed the public demo once: `docker compose -f docker-compose.prod.yml run --rm api python -m app.seed`.

## Rollback

```bash
cd /opt/evalops
IMAGE_TAG=<previous-sha> docker compose -f docker-compose.prod.yml up -d --wait
```

Migrations are additive; if one must be reverted: `docker compose ... run --rm api alembic downgrade -1`.

## Proof of deployment

Add to the README: the URL, a screenshot of the live app, and a link to a green `Deploy` run.
Stop the instance after the review period to avoid costs (`aws ec2 stop-instances`).

## Stretch: ECS Fargate + RDS

Same images; RDS Postgres via `DATABASE_URL`; ALB with ACM certificate; two services (api,
worker) and a one-off migration task per deploy.
