package com.example.entity.web;

import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import com.example.constants.AppConstants;
import com.example.entity.service.IEntityService;
import com.example.entity.utils.EntityConstants;

@RestController
@RequestMapping(value = "/api/v1/entities")
public class EntityController {

    @Autowired
    private IEntityService entityService;

    @GetMapping(value = "/getChildren")
    public RestResponse getEntityList(
            @RequestHeader(AppConstants.AUTHORIZATION) String ssoToken,
            @RequestHeader(AppConstants.CALLER_IDENTITY) String callerRef) {
        // Implementation
        return null;
    }

    @GetMapping(value = EntityConstants.GET_ENTITY_FLAGS_URL)
    @ResponseStatus(HttpStatus.OK)
    public RestResponse getEntityFlags(
            @RequestHeader(value = AppConstants.ENTITY_ID, required = true) String entityId) {
        // Implementation
        return null;
    }

    @PostMapping(value = EntityConstants.SET_ENTITY_FLAGS_URL)
    @ResponseStatus(HttpStatus.OK)
    public RestResponse setEntityFlags(
            @RequestHeader(value = AppConstants.ENTITY_ID, required = true) String entityId,
            @RequestBody Object entitySettings) {
        // Implementation
        return null;
    }
}
