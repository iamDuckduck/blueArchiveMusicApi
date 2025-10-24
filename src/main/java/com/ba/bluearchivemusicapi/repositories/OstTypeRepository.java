package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.OstType;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.repository.CrudRepository;

public interface OstTypeRepository extends CrudRepository<OstType, Long> {
    OstType findByName(String name);
    Iterable<OstType> findAllByOrderByVolumeAsc();

    @EntityGraph(attributePaths = {"ostList"})
    OstType findByVolume(Integer volumeNumber);
}
