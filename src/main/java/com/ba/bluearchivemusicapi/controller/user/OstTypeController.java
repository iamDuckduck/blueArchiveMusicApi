package com.ba.bluearchivemusicapi.controller.user;

import com.ba.bluearchivemusicapi.dtos.OstTypeDTO;
import com.ba.bluearchivemusicapi.service.OstTypeService;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController()
@RequestMapping("/user/ostType")
@AllArgsConstructor
public class OstTypeController {
    private final OstTypeService ostTypeService;

    @CrossOrigin
    @GetMapping("")
    public ResponseEntity<List<OstTypeDTO>> getAll() {
        List<OstTypeDTO> image_url = ostTypeService.getAll();
        return ResponseEntity.ok(image_url);
    }
}
