package com.ba.bluearchivemusicapi.controller.user;

import com.ba.bluearchivemusicapi.dtos.search.MusicSearchResponseDTO;
import com.ba.bluearchivemusicapi.service.MusicSearchService;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(
        name = "Search",
        description = "music search"
)
@RestController
@RequestMapping("/user/search")
@AllArgsConstructor
public class MusicSearchController {
    private final MusicSearchService musicSearchService;

    @GetMapping
    public ResponseEntity<MusicSearchResponseDTO> search(@RequestParam String query) {
        return ResponseEntity.ok(musicSearchService.search(query));
    }
}
