package com.ba.bluearchivemusicapi.controller.admin;

import com.ba.bluearchivemusicapi.dtos.OstDTO;
import com.ba.bluearchivemusicapi.dtos.OstEditDTO;
import com.ba.bluearchivemusicapi.dtos.OstUploadDTO;
import com.ba.bluearchivemusicapi.service.OstService;
import jakarta.validation.Valid;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController("adminOstController")
@RequestMapping("/admin/ost")
@AllArgsConstructor
public class OstController {
    private final OstService ostService;

    @PostMapping("/upload")
    public ResponseEntity<String> upload(@Valid @ModelAttribute OstUploadDTO ostUploadDTO) {
        ostService.upload(ostUploadDTO);
        return ResponseEntity.ok("uploaded");
    }

//    @GetMapping()
//    public ResponseEntity<Page<OstDTO>> getOst(
//            @RequestParam Integer page,
//            @RequestParam Integer size,
//            @RequestParam(defaultValue = "")String field,
//            @RequestParam(defaultValue = "") String sort) {
//        Page<OstDTO> ostDTOPage = ostService.pageQuery(page, size, field, sort);
//        return ResponseEntity.ok(ostDTOPage);
//    }

    @PutMapping("/edit/{id}")
    public ResponseEntity<OstDTO> edit(@PathVariable Long id, @Valid @ModelAttribute OstEditDTO ostEditDTO ) {
        OstDTO ostDTO = ostService.edit(id, ostEditDTO);
        return ResponseEntity.ok(ostDTO);
    }
}

