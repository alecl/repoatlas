# ── Build stage ──────────────────────────────────────────────
FROM eclipse-temurin:17-jdk-alpine AS build
WORKDIR /app
COPY pom.xml .
COPY common/pom.xml common/
COPY accounts/pom.xml accounts/
COPY cards/pom.xml cards/
COPY loans/pom.xml loans/
# Download dependencies first (layer cache)
RUN apk add --no-cache maven \
    && mvn dependency:go-offline -B -q || true
COPY . .
RUN mvn clean package -DskipTests -B -q

# ── Runtime: accounts ───────────────────────────────────────
FROM eclipse-temurin:17-jre-alpine AS accounts
WORKDIR /app
COPY --from=build /app/accounts/target/accounts-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]

# ── Runtime: cards ──────────────────────────────────────────
FROM eclipse-temurin:17-jre-alpine AS cards
WORKDIR /app
COPY --from=build /app/cards/target/cards-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 9000
ENTRYPOINT ["java", "-jar", "app.jar"]

# ── Runtime: loans ──────────────────────────────────────────
FROM eclipse-temurin:17-jre-alpine AS loans
WORKDIR /app
COPY --from=build /app/loans/target/loans-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8090
ENTRYPOINT ["java", "-jar", "app.jar"]
