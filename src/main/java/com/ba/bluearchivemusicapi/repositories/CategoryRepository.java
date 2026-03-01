package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.Category;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CategoryRepository extends JpaRepository<Category,Integer> {
    Category findByCategory(String category);
}
