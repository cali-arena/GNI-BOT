# apps/whatsapp-bot - Node.js + Baileys (TypeScript)
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install

COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# Production image
FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY --from=builder /app/dist ./dist

# Persistent Baileys auth state (mount a volume so session survives restarts)
ENV AUTH_FOLDER=/data/wa-auth
VOLUME ["/data/wa-auth"]

EXPOSE 3000

CMD ["node", "dist/index.js"]
