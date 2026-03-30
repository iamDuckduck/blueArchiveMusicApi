package com.ba.bluearchivemusicapi.controller.user;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import com.ba.bluearchivemusicapi.service.SongService;

import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;

@Tag(
        name = "Songs",
        description = "songs management"
)
@RestController("UserSongController")
@RequestMapping("/user/song")
@AllArgsConstructor
public class SongController {

    private final SongService songService;

    @GetMapping("/random")
    public ResponseEntity<SongDTO> getRandomSong() {
        SongDTO randomSong = songService.getRandomSong();
        return ResponseEntity.ok(randomSong);
    }
}
