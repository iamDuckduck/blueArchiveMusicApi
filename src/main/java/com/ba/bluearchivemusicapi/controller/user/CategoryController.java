package com.ba.bluearchivemusicapi.controller.user;

import com.ba.bluearchivemusicapi.dtos.category.CategoryWithAlbumInfoDTO;
import com.ba.bluearchivemusicapi.service.CategoryService;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.bind.annotation.CrossOrigin;
import java.util.List;

@Tag(name = "Category", description = "Category management")
@RestController("UserCategoryController")
@RequestMapping("/user/categories")
@AllArgsConstructor
public class CategoryController {

	private final CategoryService categoryService;

	@GetMapping("/details")
	public ResponseEntity<List<CategoryWithAlbumInfoDTO>> getAllCategoriesWithAlbums() {
		List<CategoryWithAlbumInfoDTO> categories = categoryService.getAllCategoriesWithAlbums();
		return ResponseEntity.ok(categories);
	}
}