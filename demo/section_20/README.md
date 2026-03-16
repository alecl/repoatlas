# Demo: EazyBank Spring Boot Microservices

Demo Java project showcasing all RepoAtlas codeanalyzer resolution features. Derived from [eazybytes/microservices](https://github.com/eazybytes/microservices) section_20 (accounts, cards, loans + common module).

This project compiles and runs as 3 standalone Spring Boot services with H2 in-memory databases — no Eureka, Config Server, Kafka, Redis, or Keycloak required.

## Running the Demo

### Prerequisites

- Java 17+ (`JAVA_HOME` set)
- Docker & Docker Compose (optional, for containerized run)

### Local Build & Run

```bash
cd demo/section_20

# Build all modules
./mvnw clean package -DskipTests

# Start services (3 terminals)
java -jar cards/target/cards-0.0.1-SNAPSHOT.jar     # port 9000
java -jar loans/target/loans-0.0.1-SNAPSHOT.jar     # port 8090
java -jar accounts/target/accounts-0.0.1-SNAPSHOT.jar  # port 8080
```

### Docker Compose

```bash
cd demo/section_20
docker compose up --build
```

Cards and loans start first; accounts waits for their health checks.

### Verification

```bash
# Health checks
curl http://localhost:9000/actuator/health   # cards
curl http://localhost:8090/actuator/health   # loans
curl http://localhost:8080/actuator/health   # accounts

# Swagger UI
# http://localhost:8080/swagger-ui.html  (accounts)
# http://localhost:9000/swagger-ui.html  (cards)
# http://localhost:8090/swagger-ui.html  (loans)
```

## Resolver Feature Map

Each subsection below maps to a specific RepoAtlas resolver and shows which Spring pattern in this codebase exercises it. This is the inventory of what the analyzer can trace statically — without compiling or running the code.

### ConstantResolver + PathResolver — Constant Chaining
- `ApiConstants.BASE_PATH = "/api"` (common module)
- `AccountsConstants.ACCOUNTS_BASE = ApiConstants.BASE_PATH` (cross-class chain)
- `@RequestMapping(path = AccountsConstants.ACCOUNTS_BASE)` (annotation value resolution)
- `@GetMapping(AccountsConstants.FETCH_URL)` (endpoint path constants)
- Same pattern in CardsConstants/LoansConstants

### AutowireResolver — @Qualifier + @Primary Precedence
- `IAccountsService` has two implementations: `AccountsServiceImpl` (`@Primary`) and `AccountsServiceAuditImpl` (`@Service("audit")`)
- `AccountsController` uses `@Autowired @Qualifier("audit")` → the analyzer correctly resolves to `AccountsServiceAuditImpl`, matching Spring's rule that an explicit qualifier takes precedence over `@Primary`

### AutowireResolver — @Primary Disambiguation
- `ICardsService` has two implementations: `CardsServiceImpl` (@Primary) and `CardsServiceCacheImpl`
- `CardsController` uses constructor injection → resolver picks the @Primary impl

### AutowireResolver — Constructor Injection
- `CardsController(ICardsService)` — single constructor, no @Autowired needed
- `LoansController(ILoansService)` — single implementation, unambiguous
- All service impls use explicit constructors (Lombok @AllArgsConstructor removed)

### PropertyResolver — @Value Placeholders
- `@Value("${build.version}")` — simple placeholder (all controllers)
- `@Value("${eazybank.accounts.base-url}")` — service-specific key (AccountsController)
- `@Value("${loans.max-amount:500000}")` — placeholder with default fallback (LoansController)

### TypeResolver + ImportResolver
- Cross-package imports: constants classes importing `com.eazybytes.common.constants.ApiConstants`
- Controller → service interface → entity → repository type chains
- JDK, Spring, and project-internal import classification

## Analyzer Verification

```bash
# Run the analyzer (from repo root)
uv run --frozen --exclude-newer 2026-03-11 python app/src/app/java_analyze.py demo/section_20/ --recursive --format markdown
```

Property resolution requires explicit loading (not auto-discovered by CLI):

```python
from app.src.codeanalyzer.analyzer import JavaAnalyzer
analyzer = JavaAnalyzer()
analyzer.parse_directory("demo/section_20/")
for svc in ["accounts", "cards", "loans"]:
    analyzer.property_resolver.load_properties_file(
        f"demo/section_20/{svc}/src/main/resources/application.properties"
    )
analyzer._resolve_all_references()
```
