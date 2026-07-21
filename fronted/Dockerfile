# Frontend DEV: Angular dev-server (ng serve) με hot reload μέσα σε Docker.
FROM node:22-alpine

WORKDIR /app

# Πρώτα τα manifests ώστε το npm install να μπαίνει στο cache.
COPY package*.json ./
RUN npm install

# Ο κώδικας έρχεται κανονικά από bind mount στο compose (για live αλλαγές),
# αλλά τον αντιγράφουμε κι εδώ ώστε το image να τρέχει και χωρίς mount.
COPY . .

EXPOSE 4200

# --host 0.0.0.0  : προσβάσιμο έξω από το container
# --poll 2000     : file polling — απαραίτητο για hot reload πάνω σε bind mounts
#                   (τα filesystem events συχνά δεν περνούν Docker/Windows)
# --proxy-config  : προωθεί /api και /ws στο backend service (βλ. proxy.conf.json)
CMD ["npm", "start", "--", "--host", "0.0.0.0", "--poll", "2000", "--proxy-config", "proxy.conf.json"]
