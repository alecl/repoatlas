package com.eazybytes.cards.constants;

import com.eazybytes.common.constants.ApiConstants;

public final class CardsConstants {

    private CardsConstants() {
        // restrict instantiation
    }

    public static final String CARDS_BASE = ApiConstants.BASE_PATH;
    public static final String CREATE_URL = "/create";
    public static final String FETCH_URL = "/fetch";
    public static final String UPDATE_URL = "/update";
    public static final String DELETE_URL = "/delete";

    public static final String  CREDIT_CARD = "Credit Card";
    public static final int  NEW_CARD_LIMIT = 1_00_000;
    public static final String  STATUS_201 = "201";
    public static final String  MESSAGE_201 = "Card created successfully";
    public static final String  STATUS_200 = "200";
    public static final String  MESSAGE_200 = "Request processed successfully";
    public static final String  STATUS_417 = "417";
    public static final String  MESSAGE_417_UPDATE= "Update operation failed. Please try again or contact Dev team";
    public static final String  MESSAGE_417_DELETE= "Delete operation failed. Please try again or contact Dev team";

}
