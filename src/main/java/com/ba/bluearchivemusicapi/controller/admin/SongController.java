package com.ba.bluearchivemusicapi.controller.admin;

import com.ba.bluearchivemusicapi.dtos.song.SongDTO;
import com.ba.bluearchivemusicapi.dtos.song.SongUploadDTO;
import com.ba.bluearchivemusicapi.service.SongService;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@Tag(
        name = "Songs",
        description = "songs management"
)
@RestController
@RequestMapping("/admin/song")
@AllArgsConstructor
public class SongController {

    private final SongService songService;

    @PostMapping("/upload")
    public ResponseEntity<SongDTO> uploadSong(@Valid @ModelAttribute SongUploadDTO songUploadDTO) {
        SongDTO uploadedDto = songService.uploadSong(songUploadDTO);
        return ResponseEntity.ok(uploadedDto);
    }
}
