# Java Spring Analysis Results

## Summary

**Total classes**: 67

**API Client Classes:**
- com.eazybytes.accounts.service.client.CardsFeignClient

- com.eazybytes.accounts.service.client.LoansFeignClient

**controller**: 7, **service**: 10, **repository**: 4, **dto**: 14, **entity**: 7, **mapper**: 4, **api_client**: 2, **exception**: 6, **other**: 13

## Controllers

### LoansController

- **Package**: `com.eazybytes.loans.controller`
- **File Path**: `main/java/com/eazybytes/loans/controller/LoansController.java`
- **Base Endpoint Path**: `LoansConstants.LOANS_BASE`

#### Endpoints

| HTTP Method | Path | Method |
|------------|------|--------|
| POST | `LoansConstants.LOANS_BASE/create` | `createLoan` |
| GET | `LoansConstants.LOANS_BASE/fetch` | `fetchLoanDetails` |
| GET | `LoansConstants.LOANS_BASE/build-info` | `getBuildInfo` |
| GET | `LoansConstants.LOANS_BASE/java-version` | `getJavaVersion` |
| GET | `LoansConstants.LOANS_BASE/contact-info` | `getContactInfo` |
| PUT | `LoansConstants.LOANS_BASE/update` | `updateLoanDetails` |
| DELETE | `LoansConstants.LOANS_BASE/delete` | `deleteLoanDetails` |

#### Service Dependencies

| Type | Superclass | Name | Qualifier |
|------|------------|------|-----------|
| `LoansServiceImpl` | `ILoansService` | `iLoansService` |  |

#### Service Method Calls

| Controller Method | Service | Service Method | Args |
|-------------------|---------|----------------|------|
| `createLoan` | `iLoansService` | `createLoan` | mobileNumber |
| `fetchLoanDetails` | `iLoansService` | `fetchLoan` | mobileNumber |
| `updateLoanDetails` | `iLoansService` | `updateLoan` | loansDto |
| `deleteLoanDetails` | `iLoansService` | `deleteLoan` | mobileNumber |

### GlobalExceptionHandler

- **Package**: `com.eazybytes.loans.exception`
- **File Path**: `main/java/com/eazybytes/loans/exception/GlobalExceptionHandler.java`
- **Base Endpoint Path**: ``

### CardsController

- **Package**: `com.eazybytes.cards.controller`
- **File Path**: `main/java/com/eazybytes/cards/controller/CardsController.java`
- **Base Endpoint Path**: `CardsConstants.CARDS_BASE`

#### Endpoints

| HTTP Method | Path | Method |
|------------|------|--------|
| POST | `CardsConstants.CARDS_BASE/create` | `createCard` |
| GET | `CardsConstants.CARDS_BASE/fetch` | `fetchCardDetails` |
| GET | `CardsConstants.CARDS_BASE/build-info` | `getBuildInfo` |
| GET | `CardsConstants.CARDS_BASE/java-version` | `getJavaVersion` |
| GET | `CardsConstants.CARDS_BASE/contact-info` | `getContactInfo` |
| PUT | `CardsConstants.CARDS_BASE/update` | `updateCardDetails` |
| DELETE | `CardsConstants.CARDS_BASE/delete` | `deleteCardDetails` |

#### Service Dependencies

| Type | Superclass | Name | Qualifier |
|------|------------|------|-----------|
| `CardsServiceImpl` | `ICardsService` | `iCardsService` |  |

#### Service Method Calls

| Controller Method | Service | Service Method | Args |
|-------------------|---------|----------------|------|
| `createCard` | `iCardsService` | `createCard` | mobileNumber |
| `fetchCardDetails` | `iCardsService` | `fetchCard` | mobileNumber |
| `updateCardDetails` | `iCardsService` | `updateCard` | cardsDto |
| `deleteCardDetails` | `iCardsService` | `deleteCard` | mobileNumber |

### GlobalExceptionHandler

- **Package**: `com.eazybytes.cards.exception`
- **File Path**: `main/java/com/eazybytes/cards/exception/GlobalExceptionHandler.java`
- **Base Endpoint Path**: ``

### CustomerController

- **Package**: `com.eazybytes.accounts.controller`
- **File Path**: `main/java/com/eazybytes/accounts/controller/CustomerController.java`
- **Base Endpoint Path**: `AccountsConstants.ACCOUNTS_BASE`

#### Endpoints

| HTTP Method | Path | Method |
|------------|------|--------|
| GET | `AccountsConstants.ACCOUNTS_BASE/fetchCustomerDetails` | `fetchCustomerDetails` |

#### Service Dependencies

| Type | Superclass | Name | Qualifier |
|------|------------|------|-----------|
| `CustomersServiceImpl` | `ICustomersService` | `iCustomersService` |  |

#### Service Method Calls

| Controller Method | Service | Service Method | Args |
|-------------------|---------|----------------|------|
| `fetchCustomerDetails` | `iCustomersService` | `fetchCustomerDetails` | mobileNumber, correlationId |

### AccountsController

- **Package**: `com.eazybytes.accounts.controller`
- **File Path**: `main/java/com/eazybytes/accounts/controller/AccountsController.java`
- **Base Endpoint Path**: `AccountsConstants.ACCOUNTS_BASE`

#### Endpoints

| HTTP Method | Path | Method |
|------------|------|--------|
| POST | `AccountsConstants.ACCOUNTS_BASE/create` | `createAccount` |
| GET | `AccountsConstants.ACCOUNTS_BASE/fetch` | `fetchAccountDetails` |
| GET | `AccountsConstants.ACCOUNTS_BASE/build-info` | `getBuildInfo` |
| GET | `AccountsConstants.ACCOUNTS_BASE/java-version` | `getJavaVersion` |
| GET | `AccountsConstants.ACCOUNTS_BASE/contact-info` | `getContactInfo` |
| PUT | `AccountsConstants.ACCOUNTS_BASE/update` | `updateAccountDetails` |
| DELETE | `AccountsConstants.ACCOUNTS_BASE/delete` | `deleteAccountDetails` |

#### Service Dependencies

| Type | Superclass | Name | Qualifier |
|------|------------|------|-----------|
| `AccountsServiceAuditImpl` | `IAccountsService` | `iAccountsService` | audit |

#### Service Method Calls

| Controller Method | Service | Service Method | Args |
|-------------------|---------|----------------|------|
| `createAccount` | `iAccountsService` | `createAccount` | customerDto |
| `fetchAccountDetails` | `iAccountsService` | `fetchAccount` | mobileNumber |
| `updateAccountDetails` | `iAccountsService` | `updateAccount` | customerDto |
| `deleteAccountDetails` | `iAccountsService` | `deleteAccount` | mobileNumber |

### GlobalExceptionHandler

- **Package**: `com.eazybytes.accounts.exception`
- **File Path**: `main/java/com/eazybytes/accounts/exception/GlobalExceptionHandler.java`
- **Base Endpoint Path**: ``

## Services

### ILoansService

- **Package**: `com.eazybytes.loans.service`
- **File Path**: `main/java/com/eazybytes/loans/service/ILoansService.java`
- **Fully Qualified Name**: `com.eazybytes.loans.service.ILoansService`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `void` | `createLoan` | String mobileNumber |
| `LoansDto` | `fetchLoan` | String mobileNumber |
| `boolean` | `updateLoan` | LoansDto loansDto |
| `boolean` | `deleteLoan` | String mobileNumber |

### LoansServiceImpl

- **Package**: `com.eazybytes.loans.service.impl`
- **File Path**: `main/java/com/eazybytes/loans/service/impl/LoansServiceImpl.java`
- **Fully Qualified Name**: `com.eazybytes.loans.service.impl.LoansServiceImpl`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `void` | `createLoan` | String mobileNumber |
| `Loans` | `createNewLoan` | String mobileNumber |
| `LoansDto` | `fetchLoan` | String mobileNumber |
| `boolean` | `updateLoan` | LoansDto loansDto |
| `boolean` | `deleteLoan` | String mobileNumber |

### ICardsService

- **Package**: `com.eazybytes.cards.service`
- **File Path**: `main/java/com/eazybytes/cards/service/ICardsService.java`
- **Fully Qualified Name**: `com.eazybytes.cards.service.ICardsService`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `void` | `createCard` | String mobileNumber |
| `CardsDto` | `fetchCard` | String mobileNumber |
| `boolean` | `updateCard` | CardsDto cardsDto |
| `boolean` | `deleteCard` | String mobileNumber |

### CardsServiceImpl

- **Package**: `com.eazybytes.cards.service.impl`
- **File Path**: `main/java/com/eazybytes/cards/service/impl/CardsServiceImpl.java`
- **Fully Qualified Name**: `com.eazybytes.cards.service.impl.CardsServiceImpl`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `void` | `createCard` | String mobileNumber |
| `Cards` | `createNewCard` | String mobileNumber |
| `CardsDto` | `fetchCard` | String mobileNumber |
| `boolean` | `updateCard` | CardsDto cardsDto |
| `boolean` | `deleteCard` | String mobileNumber |

### CardsServiceCacheImpl

- **Package**: `com.eazybytes.cards.service.impl`
- **File Path**: `main/java/com/eazybytes/cards/service/impl/CardsServiceCacheImpl.java`
- **Fully Qualified Name**: `com.eazybytes.cards.service.impl.CardsServiceCacheImpl`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `void` | `createCard` | String mobileNumber |
| `Cards` | `createNewCard` | String mobileNumber |
| `CardsDto` | `fetchCard` | String mobileNumber |
| `boolean` | `updateCard` | CardsDto cardsDto |
| `boolean` | `deleteCard` | String mobileNumber |

### ICustomersService

- **Package**: `com.eazybytes.accounts.service`
- **File Path**: `main/java/com/eazybytes/accounts/service/ICustomersService.java`
- **Fully Qualified Name**: `com.eazybytes.accounts.service.ICustomersService`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `CustomerDetailsDto` | `fetchCustomerDetails` | String mobileNumber, String correlationId |

### IAccountsService

- **Package**: `com.eazybytes.accounts.service`
- **File Path**: `main/java/com/eazybytes/accounts/service/IAccountsService.java`
- **Fully Qualified Name**: `com.eazybytes.accounts.service.IAccountsService`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `void` | `createAccount` | CustomerDto customerDto |
| `CustomerDto` | `fetchAccount` | String mobileNumber |
| `boolean` | `updateAccount` | CustomerDto customerDto |
| `boolean` | `deleteAccount` | String mobileNumber |
| `boolean` | `updateCommunicationStatus` | Long accountNumber |

### CustomersServiceImpl

- **Package**: `com.eazybytes.accounts.service.impl`
- **File Path**: `main/java/com/eazybytes/accounts/service/impl/CustomersServiceImpl.java`
- **Fully Qualified Name**: `com.eazybytes.accounts.service.impl.CustomersServiceImpl`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `CustomerDetailsDto` | `fetchCustomerDetails` | String mobileNumber, String correlationId |

### AccountsServiceAuditImpl

- **Package**: `com.eazybytes.accounts.service.impl`
- **File Path**: `main/java/com/eazybytes/accounts/service/impl/AccountsServiceAuditImpl.java`
- **Fully Qualified Name**: `com.eazybytes.accounts.service.impl.AccountsServiceAuditImpl`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `void` | `createAccount` | CustomerDto customerDto |
| `Accounts` | `createNewAccount` | Customer customer |
| `CustomerDto` | `fetchAccount` | String mobileNumber |
| `boolean` | `updateAccount` | CustomerDto customerDto |
| `boolean` | `deleteAccount` | String mobileNumber |
| `boolean` | `updateCommunicationStatus` | Long accountNumber |

### AccountsServiceImpl

- **Package**: `com.eazybytes.accounts.service.impl`
- **File Path**: `main/java/com/eazybytes/accounts/service/impl/AccountsServiceImpl.java`
- **Fully Qualified Name**: `com.eazybytes.accounts.service.impl.AccountsServiceImpl`

#### Methods

| Return Type | Method | Parameters |
|-------------|--------|------------|
| `void` | `createAccount` | CustomerDto customerDto |
| `void` | `sendCommunication` | Accounts account, Customer customer |
| `Accounts` | `createNewAccount` | Customer customer |
| `CustomerDto` | `fetchAccount` | String mobileNumber |
| `boolean` | `updateAccount` | CustomerDto customerDto |
| `boolean` | `deleteAccount` | String mobileNumber |
| `boolean` | `updateCommunicationStatus` | Long accountNumber |
