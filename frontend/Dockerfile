
FROM node:18-alpine

WORKDIR /app

COPY package.json ./

# Force reinstall dependencies
RUN npm install

COPY . .

CMD ["npm", "start"]
