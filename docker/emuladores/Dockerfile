# firebase-tools exige Java 21+; o Debian bookworm só traz o 17, por isso a base é trixie.
FROM node:22-trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g firebase-tools
WORKDIR /emuladores
COPY firebase.json ./
CMD ["firebase", "emulators:start", "--only", "auth,firestore", "--project", "demo-rpa"]
