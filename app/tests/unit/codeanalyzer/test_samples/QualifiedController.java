package com.example.web;

import java.util.List;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;

@org.springframework.web.bind.annotation.RestController
@org.springframework.web.bind.annotation.RequestMapping("/api/users")
public class QualifiedController {

    @org.springframework.beans.factory.annotation.Autowired
    private UserService userService;

    @org.springframework.web.bind.annotation.GetMapping("")
    public List<User> getAllUsers() {
        return userService.findAll();
    }

    @org.springframework.web.bind.annotation.GetMapping("/{id}")
    public ResponseEntity<User> getUser(
        @org.springframework.web.bind.annotation.PathVariable("id") Long id) {
        return ResponseEntity.ok(userService.findById(id));
    }
}
