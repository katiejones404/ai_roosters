# Development Dockerfile for React with hot reloading
FROM node:18-alpine

# Set working directory
WORKDIR /app

# Copy package files first
COPY package*.json ./

# Install dependenceis
RUN npm install

COPY . .

# Vite dev server port
EXPOSE 5173

CMD ["npm","run", "dev", "--", "--host"]