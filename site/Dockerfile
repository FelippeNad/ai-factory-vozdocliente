FROM node:22.16.0-alpine
WORKDIR /app
COPY --chown=node:node server.js ./
COPY --chown=node:node public ./public
USER node
ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "server.js"]
