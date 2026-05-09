package com.ba.bluearchivemusicapi.controller.user;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import com.ba.bluearchivemusicapi.service.SongService;

import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;

import java.util.List;

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
    @CrossOrigin(origins = "http://localhost:5173")
    public ResponseEntity<SongDTO> getRandomSong() {
        SongDTO randomSong = songService.getRandomSong();
        return ResponseEntity.ok(randomSong);
    }

    @GetMapping("/random/list")
    @CrossOrigin(origins = "http://localhost:5173")
    public ResponseEntity<List<SongDTO>> getListRandomSong() {
        List<SongDTO> randomSongList = songService.getRandomSongList();
        return ResponseEntity.ok(randomSongList);
    }

    @PostMapping("/{id}/play")
    @CrossOrigin(origins = "http://localhost:5173")
    public ResponseEntity<Void> incrementPlayCount(@PathVariable Long id) {
        songService.incrementSongPlayCount(id);
        return ResponseEntity.accepted().build();
    }
}
