package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Category;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface CategoryRepository extends JpaRepository<Category,Integer> {
    Category findByCategory(String category);
    Optional<Category> findById(Long id);
}
