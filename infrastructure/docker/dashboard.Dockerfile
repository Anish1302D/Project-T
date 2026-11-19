FROM node:22-alpine AS builder

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml tsconfig.base.json turbo.json ./
COPY packages/contracts/package.json packages/contracts/tsconfig.json ./packages/contracts/
COPY packages/shared-utils/package.json packages/shared-utils/tsconfig.json ./packages/shared-utils/
COPY packages/shared-ui/package.json packages/shared-ui/tsconfig.json ./packages/shared-ui/
COPY apps/dashboard/package.json apps/dashboard/tsconfig.json ./apps/dashboard/

RUN pnpm install --frozen-lockfile --filter @project-t/dashboard...

COPY packages/contracts ./packages/contracts
COPY packages/shared-utils ./packages/shared-utils
COPY packages/shared-ui ./packages/shared-ui
COPY apps/dashboard ./apps/dashboard

RUN pnpm --filter @project-t/dashboard... build

FROM nginx:1.27-alpine
COPY infrastructure/docker/nginx.dashboard.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/apps/dashboard/dist /usr/share/nginx/html

EXPOSE 80
