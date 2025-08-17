package com.ba.bluearchivemusicapi.controller.user;


import com.ba.bluearchivemusicapi.common.constant.SortConstant;
import com.ba.bluearchivemusicapi.dtos.OstPageDTO;
import com.ba.bluearchivemusicapi.service.OstService;
import lombok.AllArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController("userOstController")
@RequestMapping("/user/ost")
@AllArgsConstructor
public class OstController {
    private final OstService ostService;

    @GetMapping("/image/{id}")
    public ResponseEntity<String> getImage(@PathVariable Long id) {
        String image_url = ostService.getImageById(id);
        return ResponseEntity.ok(image_url);
    }

    @CrossOrigin
    @GetMapping("/audio/{id}")
    public ResponseEntity<String> getAudio(@PathVariable Long id) {
        String image_url = ostService.getAudioById(id);
        return ResponseEntity.ok(image_url);
    }

    @CrossOrigin
    @GetMapping()
    // TODO add default value?
    public ResponseEntity<Page<OstPageDTO>> getOst(@RequestParam Integer page,
                                                   @RequestParam Integer size,
                                                   @RequestParam(defaultValue = SortConstant.DEFAULT_SORT_FIELD) String sortField,
                                                   @RequestParam(defaultValue = SortConstant.SORT_DIRECTION_ASC) String sortDirection,
                                                   @RequestParam(required = false) String filterField,
                                                   @RequestParam(required = false) String filterValue) {

        Page<OstPageDTO> ostDTOPage = ostService.pageQuery(page, size, sortField, sortDirection, filterField, filterValue);
        return ResponseEntity.ok(ostDTOPage);
    }
}

