package com.ba.bluearchivemusicapi.controller.admin;

import com.ba.bluearchivemusicapi.dtos.category.CategoryDTO;
import com.ba.bluearchivemusicapi.dtos.category.CategoryUploadDTO;
import com.ba.bluearchivemusicapi.service.CategoryService;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@Tag(
        name = "Category",
        description = "Category management"
)
@RestController("/admin/category")
@AllArgsConstructor
public class CategoryController {

    private final CategoryService categoryService;

    @Operation(
        summary = "Upload a new category",
        description = "Creates a new category and returns the saved category.",
        requestBody = @io.swagger.v3.oas.annotations.parameters.RequestBody(
            description = "Category upload data",
            required = true,
            content = @Content(
                schema = @Schema(implementation = CategoryUploadDTO.class)
            )
        ),
            responses = {
                    @ApiResponse(
                            responseCode = "200",
                            description = "Category uploaded successfully",
                            content = @Content(schema = @Schema(implementation = CategoryDTO.class))
                    ),
                    @ApiResponse(
                            responseCode = "400",
                            description = "Invalid input data",
                            content = @Content(mediaType = "text/plain")
                    ),
                    @ApiResponse(
                            responseCode = "409",
                            description = "Category already exists",
                            content =  @Content(mediaType = "text/plain")
                    )
            }
    )
    @PostMapping("/upload")
    public ResponseEntity<CategoryDTO> uploadCategory(@Valid @RequestBody CategoryUploadDTO categoryUploadDTO) {
        CategoryDTO savedCategory = categoryService.saveCategory(categoryUploadDTO);

        return ResponseEntity.ok(savedCategory);
    }
}
