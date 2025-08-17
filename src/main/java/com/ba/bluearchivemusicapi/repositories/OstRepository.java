package com.ba.bluearchivemusicapi.repositories;

import com.ba.bluearchivemusicapi.entities.OST;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.repository.CrudRepository;


public interface OstRepository extends CrudRepository<OST, Long>, JpaSpecificationExecutor<OST> {
}

