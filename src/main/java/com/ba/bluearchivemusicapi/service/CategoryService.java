package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.common.exception.CategoryAlreadyExistsException;
import com.ba.bluearchivemusicapi.dtos.category.CategoryDTO;
import com.ba.bluearchivemusicapi.dtos.category.CategoryUploadDTO;
import com.ba.bluearchivemusicapi.entities.Category;
import com.ba.bluearchivemusicapi.mappers.CategoryMapper;
import com.ba.bluearchivemusicapi.repositories.CategoryRepository;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@AllArgsConstructor
public class CategoryService {

    private final CategoryRepository categoryRepository;

    private final CategoryMapper categoryMapper;

    public CategoryDTO saveCategory(CategoryUploadDTO categoryUploadDTO) {
        if (categoryRepository.findByCategory(categoryUploadDTO.getCategoryName()) != null)
            throw new CategoryAlreadyExistsException("Category already exists");


        Category category = Category.builder()
                .category(categoryUploadDTO.getCategoryName())
                .build();

        categoryRepository.save(category);
        return categoryMapper.categoryToCategoryDTO(category);
    }
}
